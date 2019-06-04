import mock
from pyVmomi import vim

from cvfm.clients import VCenterAPIClient
from tests import utils


class VCenterAPIMockClient(VCenterAPIClient):
    def __init__(self):
        self.portgroups = {}
        self.hosts = {}

    def create_dpg(self, vmware_dpg):
        event = mock.Mock(spec=vim.event.DVPortgroupCreatedEvent())
        event.net.network = vmware_dpg
        self.portgroups[vmware_dpg.key] = vmware_dpg
        return utils.wrap_into_update_set(event=event)

    def destroy_dpg(self, vmware_dpg):
        event = mock.Mock(spec=vim.event.DVPortgroupDestroyedEvent())
        event.net.name = vmware_dpg.name
        event.dvs.name = vmware_dpg.config.distributedVirtualSwitch.name
        del self.portgroups[vmware_dpg.key]
        return utils.wrap_into_update_set(event=event)

    def create_vm(self, vmware_vm):
        for network in vmware_vm.network:
            network.vm.append(vmware_vm)
            self.portgroups[network.key] = network

        host_name = vmware_vm.runtime.host.name
        host = self.hosts.get(host_name)
        if not host:
            host = mock.Mock(vm=[])
            host.configure_mock(name=host_name)
        host.vm.append(vmware_vm)
        self.hosts[host_name] = host

        event = mock.Mock(spec=vim.event.VmCreatedEvent())
        event.vm.vm = vmware_vm
        return utils.wrap_into_update_set(event=event)

    def remove_vm(self, vmware_vm):
        for network in vmware_vm.network:
            self.portgroups[network.key].vm.remove(vmware_vm)

        host_name = vmware_vm.runtime.host.name
        self.hosts[host_name].vm.remove(vmware_vm)

        event = mock.Mock(spec=vim.event.VmRemovedEvent())
        event.vm.name = vmware_vm.name
        event.host.name = host_name
        event.host.host = self.hosts[host_name]
        return utils.wrap_into_update_set(event=event)

    def get_vms_by_portgroup(self, portgroup_key):
        return self.portgroups[portgroup_key].vm

    def add_interface(self, vmware_vm, vmware_dpg):
        vmware_vm.network.append(vmware_dpg)
        self.portgroups[vmware_dpg.key].vm.append(vmware_vm)
        return utils.create_vm_reconfigured_update(vmware_vm, "add")

    def edit_interface(self, vmware_vm, old_vmware_dpg, new_vmware_dpg):
        self.remove_interface(vmware_vm, old_vmware_dpg)
        self.add_interface(vmware_vm, new_vmware_dpg)
        return utils.create_vm_reconfigured_update(vmware_vm, "edit")

    def remove_interface(self, vmware_vm, vmware_dpg):
        vmware_vm.network.remove(vmware_dpg)
        self.portgroups[vmware_dpg.key].vm.remove(vmware_vm)
        return utils.create_vm_reconfigured_update(vmware_vm, "remove")

    def get_all_portgroups(self):
        return self.portgroups.values()