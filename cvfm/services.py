import logging
import uuid

from vnc_api import vnc_api

from cvfm.models import VirtualMachineModel
from cvfm import models
from cvfm import constants as const

logger = logging.getLogger(__name__)


class Service(object):
    def __init__(self, vcenter_api_client, vnc_api_client, database):
        self._vcenter_api_client = vcenter_api_client
        self._vnc_api_client = vnc_api_client
        self._database = database


class VirtualMachineService(Service):
    def __init__(self, vcenter_api_client, vnc_api_client, database):
        super(VirtualMachineService, self).__init__(
            vcenter_api_client, vnc_api_client, database
        )

    def get_host_model(self, host_name):
        logger.info("VirtualMachineService.get_host_model called")

    def create_vm_model(self, vmware_vm, host_model):
        logger.info("VirtualMachineService.create_vm_model called")

    def delete_vm_model(self, vm_name):
        logger.info("VirtualMachineService.delete_vm_model called")
        return VirtualMachineModel()

    def migrate_vm_model(self, vm_uuid, target_host_model):
        logger.info("VirtualMachineService.migrate_vm_model called")
        return VirtualMachineModel()

    def rename_vm_model(self, vm_uuid, new_name):
        logger.info("VirtualMachineService.rename_vm_model called")


class VirtualMachineInterfaceService(Service):
    def __init__(self, vcenter_api_client, vnc_api_client, database):
        super(VirtualMachineInterfaceService, self).__init__(
            vcenter_api_client, vnc_api_client, database
        )

    def create_vmi_models_for_vm(self, vmware_vm):
        return models.VirtualMachineInterfaceModel.from_vmware_vm(vmware_vm)

    def create_vmi_in_vnc(self, vmi_model):
        if self._vnc_api_client.read_vmi(vmi_model.uuid) is None:
            project = self._vnc_api_client.get_project()
            fabric_vn = self._vnc_api_client.read_vn(vmi_model.dpg_model.uuid)
            vnc_vmi = vmi_model.to_vnc_vmi(project, fabric_vn)
            self._vnc_api_client.create_vmi(vnc_vmi)

    def attach_vmi_to_vpg(self, vmi_model):
        vnc_vpg = self._vnc_api_client.read_vpg(vmi_model.vpg_uuid)
        vnc_vmi = self._vnc_api_client.read_vmi(vmi_model.uuid)
        vnc_vpg.add_virtual_machine_interface(vnc_vmi)
        self._vnc_api_client.update_vpg(vnc_vpg)

    def delete_vmi(self, vm_uuid, vmware_vmi=None, vmi_model=None):
        logger.info("VirtualMachineInterfaceService.delete_vmi called")

    def add_vmi(self, vm_uuid, vmware_vmi):
        logger.info("VirtualMachineInterfaceService.add_vmi called")

    def migrate_vmi(self, vmi_model, source_host_model, target_host_model):
        logger.info("VirtualMachineInterfaceService.migrate_vmi called")


class DistributedPortGroupService(Service):
    def __init__(self, vcenter_api_client, vnc_api_client, database):
        super(DistributedPortGroupService, self).__init__(
            vcenter_api_client, vnc_api_client, database
        )

    def create_dpg_model(self, vmware_dpg):
        return models.DistributePortGroupModel.from_vmware_dpg(vmware_dpg)

    def create_fabric_vn(self, dpg_model):
        project = self._vnc_api_client.get_project()
        vnc_vn = dpg_model.to_vnc_vn(project)

        self._vnc_api_client.create_vn(vnc_vn)
        logger.info("Virtual Network %s created in VNC", vnc_vn.name)

    def create_vpg_models(self, vmware_vm):
        return models.VirtualPortGroupModel.from_vmware_vm(vmware_vm)

    def create_vpg_in_vnc(self, vpg_model):
        if self._vnc_api_client.read_vpg(vpg_model.uuid) is None:
            vnc_vpg = vpg_model.to_vnc_vpg()
            self._vnc_api_client.create_vpg(vnc_vpg)

    def attach_pis_to_vpg(self, vpg_model):
        vnc_vpg = self._vnc_api_client.read_vpg(vpg_model.uuid)
        pis = self.find_matches_physical_interfaces(
            vpg_model.host_name, vpg_model.dvs_name
        )
        self._vnc_api_client.connect_physical_interfaces_to_vpg(vnc_vpg, pis)

    def find_matches_physical_interfaces(self, host_name, dvs_name):
        vnc_node = self._vnc_api_client.get_node_by_name(host_name)
        if vnc_node is None:
            return []
        vnc_ports = self._vnc_api_client.get_node_ports(vnc_node)
        vnc_ports = self.filter_node_ports_by_dvs_name(vnc_ports, dvs_name)
        return self.collect_pis_from_ports(vnc_ports)

    def filter_node_ports_by_dvs_name(self, ports, dvs_name):
        return [
            port
            for port in ports
            if self.is_dvs_in_port_annotations(port, dvs_name)
        ]

    def is_dvs_in_port_annotations(self, port, dvs_name):
        annotations = port.get_annotations().key_value_pair
        for annotation in annotations:
            if (
                annotation.value == const.DVS_ANNOTATION
                and annotation.key == dvs_name
            ):
                return True
        return False

    def collect_pis_from_ports(self, vnc_ports):
        pis = []
        for port in vnc_ports:
            port_pis = self._vnc_api_client.get_pis_by_port(port)
            pis.extend(port_pis)
        return pis

    def create_fabric_vmi_for_vm_vmi(self, vmi_model):
        logger.info(
            "DistributedPortGroupService.create_fabric_vmi_for_vm_vmi called"
        )

    def delete_fabric_vmi_for_vm_vmi(self, vmi_model):
        logger.info(
            "DistributedPortGroupService.delete_fabric_vmi_for_vm_vmi called"
        )

    def handle_vm_vmi_migration(self, vmi_model, source_host_model):
        logger.info(
            "DistributedPortGroupService.handle_vm_vmi_migration called"
        )

    def get_dvs_model(self, vmware_dvs):
        logger.info("DistributedPortGroupService.get_dvs_model called")

    def detect_vlan_change(self, vmware_dpg):
        logger.info("DistributedPortGroupService.detect_vlan_change called")
        return True

    def handle_vlan_change(self, vmware_dpg):
        logger.info("DistributedPortGroupService.handle_vlan_change called")

    def rename_dpg(self, dpg_uuid, new_dpg_name):
        logger.info("DistributedPortGroupService.rename_dpg called")

    def delete_dpg_model(self, dpg_name):
        logger.info("DistributedPortGroupService.delete_dpg_model called")

    def delete_fabric_vn(self, dpg_model):
        logger.info("DistributedPortGroupService.delete_fabric_vn called")