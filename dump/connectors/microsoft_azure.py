"""

"""
# stdlib
import json
from functools import lru_cache
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

# dependencies
from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions
# pyinfra
from pyinfra import logger
from pyinfra.connectors.base import BaseConnector
from pyinfra.progress import progress_spinner

if TYPE_CHECKING:
    PYINFRA_INVENTORY = dict[str, list[tuple[str, dict[str, str]]]]


class AzureConnector(BaseConnector):
    handles_execution = False

    @staticmethod
    def get_file(*_, **__):
        raise NotImplementedError

    @staticmethod
    def put_file(*_, **__):
        raise NotImplementedError

    @staticmethod
    def run_shell_command(*_, **__):
        raise NotImplementedError

    @staticmethod
    def query(where: dict[str, str]) -> str:
        """Generate the Resource Graph query

        Example::

            >>> AzureConnector.query(where={"location": "eastus", "resourceGroup": "dev"})

        :param where: generate a case-insensitive :samp:`where {key} in ({value})` clause per item
        """
        additional_where = []
        for key, value in where.items():
            # a naive defensive programming here to avoid KQL injection; **not** battle tested
            if not key.isalpha():
                raise ValueError(key)
            if value:
                # it might be more convenient to use regex here, but I didn't put the effort of safely escaping them
                # so a case-insensitive union will suffice for now
                additional_where += [
                    f"| where {key} in~ ('{"','".join(filter(None, value.replace("'", "''").split(",")))}')"
                ]

        # Note that I don't use Azure tags, so they are missing from this query for now
        return dedent(
            f"""\
            Resources
            | where type =~ 'microsoft.compute/VirtualMachines'
            | where properties.storageProfile.osDisk.osType == "Linux"
            | mv-expand netIf = properties.networkProfile.networkInterfaces
            {" ".join(additional_where)}
            | project resourceGroup, name, nicResourceId = tostring(netIf.id), location, zones
            | join kind=leftouter (
              Resources
              | where type =~ 'microsoft.network/NetworkInterfaces'
              | mv-expand ipConf = properties.ipConfigurations
              | where tobool(ipConf.properties.primary) == true
              | project nicResourceId = id, privateIP = tostring(ipConf.properties.privateIPAddress)
              ) on nicResourceId
            | project group = resourceGroup, hostname = name, ip = privateIP, location, zones\
            """
        )

    # I put an LRU cache because I noticed the function was called twice with the same arguments in my tests,
    # and the query is already slow enough as it is.
    @classmethod
    @lru_cache(8)
    def _azure_vm_list(cls, **where) -> PYINFRA_INVENTORY:
        """Query the Azure Resource Graph API and returns the list of VM with their main internal IP

        I chose to group them by Azure Resource Group name.
        """
        data = {}
        client = ResourceGraphClient(DefaultAzureCredential())
        with progress_spinner({"get Azure inventory"}):
            response = client.resources(
                QueryRequest(
                    query=cls.query(**where),
                    options=QueryRequestOptions(result_format="objectArray"),
                )
            )

            for row in response.data:
                # noinspection PyTypeChecker
                group = row["group"]

                if group not in data:
                    data[group] = []

                # noinspection PyTypeChecker
                data[group] += [
                    (
                        row["hostname"],
                        {
                            "ssh_hostname": row["ip"],
                            "location": row["location"],
                            "zones": row["zones"],
                            "group": group,
                        }
                    )
                ]

        return data

    @staticmethod
    def _parse_name(name: str = None) -> tuple[str, str]:
        """
        * All hosts in groups *dev* and *prod*: ``dev,prod/``
        * All hosts matching *db* or *webserver*: ``db,webserver`` (or ``/db,webserver``)
        * All hosts matching *webserver* in groups *dev* and *prod*: ``dev,prod/webserver``
        """
        groups = ""
        hosts = ""
        if name is not None:
            if "/" in name:
                groups, hosts = name.partition("/")[::2]
            else:
                hosts = name.removeprefix("/")

        return groups, hosts

    @classmethod
    def make_names_data(cls, name: str = None):
        """
        Generate inventory targets.
        """
        only_groups, only_hosts = cls._parse_name(name)
        inventory = cls._azure_vm_list(resourceGroup=only_groups, name=only_hosts)

        for group, hosts in inventory.items():
            for host, data in hosts:
                yield (
                    f"@ssh/{host}",
                    data,
                    [group, "azure"],
                )
