# Pyinfra — tips and tricks

## azure connector

Query Azure Resource Graph endpoint to list your Virtual Machines.

This use [DefaultAzureCredential](https://learn.microsoft.com/fr-fr/python/api/azure-identity/azure.identity.defaultazurecredential) to list all Virtual Machines the current identity have access to.
Usually you want to [`az login`](https://learn.microsoft.com/en-us/cli/azure/reference-index?view=azure-cli-latest#az-login), but if ran in a pipeline or through other means, be sure the underlying identity have necessary access to the [Azure Resource Graph REST API](https://learn.microsoft.com/en-us/rest/api/azure-resourcegraph/).

Example:

```shell
# list all VM
uv run pyinfra @azure debug-inventory

# list VM of the resource groups dev and pre
uv run pyinfra @azure/dev,pre/ ...

# select by VM name
uv run pyinfra @azure//vm-example,bastion ...

# by VM name and group
uv run pyinfra @azure/dev/bastion ...
```