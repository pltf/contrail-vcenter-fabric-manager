import logging
import uuid as uid

from vnc_api import vnc_api

from cvfm.exceptions import DPGCreationException

logger = logging.getLogger(__name__)


def key_to_uuid(key):
    return str(uid.uuid3(uid.NAMESPACE_DNS, key))


class VirtualMachineModel(object):
    def __init__(self):
        pass

    def get_all_vmis(self):
        return [object()]


class DistributePortGroupModel(object):
    def __init__(self, uuid, name, vlan_id, dvs_name):
        self.uuid = uuid
        self.name = name
        self.vlan_id = vlan_id
        self.dvs_name = dvs_name

    def to_vnc_vn(self, project):
        vnc_name = "{dvs_name}_{dpg_name}".format(
            dvs_name=self.dvs_name, dpg_name=self.name
        )
        vnc_vn = vnc_api.VirtualNetwork(name=vnc_name, parent_obj=project)
        vnc_vn.set_uuid(self.uuid)
        return vnc_vn

    @classmethod
    def from_vmware_dpg(cls, vmware_dpg):
        cls._validate_vlan_id(vmware_dpg)
        vlan_id = vmware_dpg.config.defaultPortConfig.vlan.vlanId
        uuid = key_to_uuid(vmware_dpg.key)
        name = vmware_dpg.name
        dvs_name = vmware_dpg.config.distributedVirtualSwitch.name
        return cls(uuid, name, vlan_id, dvs_name)

    @classmethod
    def _validate_vlan_id(cls, vmware_dpg):
        try:
            vlan_id = int(vmware_dpg.config.defaultPortConfig.vlan.vlanId)
        except (TypeError, AttributeError):
            raise DPGCreationException("VLAN ID must be a number.")
        if vlan_id == 0:
            raise DPGCreationException("VLAN ID cannot be 0.")

    def __repr__(self):
        return (
            "DistributePortGroupModel(uuid={uuid}, "
            "name={name}, vlan_id={vlan_id}, "
            "dvs_name={dvs_name})".format(
                uuid=self.uuid,
                name=self.name,
                vlan_id=self.vlan_id,
                dvs_name=self.dvs_name,
            )
        )


class VirtualPortGroupModel(object):
    def __init__(self, uuid, host_name, dvs_name):
        self.uuid = uuid
        self.host_name = host_name
        self.dvs_name = dvs_name

    def to_vnc_vpg(self):
        vnc_name = "{host_name}_{dvs_name}".format(
            host_name=self.host_name, dvs_name=self.dvs_name
        )
        vnc_vpg = vnc_api.VirtualPortGroup(name=vnc_name)
        vnc_vpg.set_uuid(self.uuid)
        return vnc_vpg

    @classmethod
    def from_vmware_vm(cls, vmware_vm):
        host_name = vmware_vm.runtime.host.name
        models = []
        for dpg in vmware_vm.network:
            dvs_name = dpg.config.distributedVirtualSwitch.name
            uuid = key_to_uuid(
                "{host_name}_{dvs_name}".format(
                    host_name=host_name, dvs_name=dvs_name
                )
            )
            models.append(cls(uuid, host_name, dvs_name))
        return models

    def __repr__(self):
        return (
            "VirtualPortGroupModel(uuid={uuid}, host_name={host_name}, "
            "dvs_name={dvs_name})".format(
                uuid=self.uuid,
                host_name=self.host_name,
                dvs_name=self.dvs_name,
            )
        )


class VirtualMachineInterfaceModel(object):
    def __init__(self):
        pass
