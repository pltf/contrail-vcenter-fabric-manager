#!/usr/bin/env python

import argparse
import logging
import os
import random
import socket
import sys

import gevent
import yaml
from cfgm_common.uve.nodeinfo.ttypes import NodeStatus, NodeStatusUVE
from pysandesh.connection_info import ConnectionState
from cfgm_common.zkclient import ZookeeperClient
from pysandesh.sandesh_base import Sandesh, SandeshConfig
from sandesh_common.vns.constants import (
    INSTANCE_ID_DEFAULT,
    Module2NodeType,
    ModuleNames,
    NodeTypeNames,
    ServiceHttpPortMap,
)
from sandesh_common.vns.ttypes import Module


from cvfm import controllers, services, synchronizers
from cvfm.clients import VCenterAPIClient, VNCAPIClient
from cvfm.database import Database
from cvfm.event_listener import EventListener
from cvfm.monitors import VMwareMonitor
from cvfm.sandesh_handler import SandeshHandler
from cvfm.supervisor import Supervisor

gevent.monkey.patch_all()


def load_config(config_file):
    with open(config_file, "r") as ymlfile:
        return yaml.load(ymlfile)


def translate_logging_level(level):
    # Default logging level during contrail deployment is SYS_NOTICE,
    # but python logging library hasn't notice level, so we have to translate
    # SYS_NOTICE to logging.INFO, because next available level is logging.WARN,
    # what is too high for normal vcenter-fabric-manager logging.
    if level == "SYS_NOTICE":
        return "SYS_INFO"
    return level


def build_context(config):
    lock = gevent.lock.BoundedSemaphore()
    update_set_queue = gevent.queue.Queue()

    database = Database()
    vcenter_api_client = VCenterAPIClient(config["vcenter"])
    vnc_api_client = VNCAPIClient(config["vnc"])

    vm_service = services.VirtualMachineService(
        vcenter_api_client, vnc_api_client, database
    )
    vmi_service = services.VirtualMachineInterfaceService(
        vcenter_api_client, vnc_api_client, database
    )
    dpg_service = services.DistributedPortGroupService(
        vcenter_api_client, vnc_api_client, database
    )
    vpg_service = services.VirtualPortGroupService(
        vcenter_api_client, vnc_api_client, database
    )

    vm_updated_handler = controllers.VmUpdatedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    vm_reconfigured_handler = controllers.VmReconfiguredHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    vm_removed_handler = controllers.VmRemovedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    vm_renamed_handler = controllers.VmRenamedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    vm_host_change_handler = controllers.HostChangeHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )

    dvportgroup_created_handler = controllers.DVPortgroupCreatedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    dvportgroup_reconfigured_handler = controllers.DVPortgroupReconfiguredHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    dvportgroup_renamed_handler = controllers.DVPortgroupRenamedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )
    dvportgroup_destroyed_handler = controllers.DVPortgroupDestroyedHandler(
        vm_service, vmi_service, dpg_service, vpg_service
    )

    handlers = [
        vm_updated_handler,
        vm_renamed_handler,
        vm_reconfigured_handler,
        vm_removed_handler,
        vm_host_change_handler,
        dvportgroup_created_handler,
        dvportgroup_reconfigured_handler,
        dvportgroup_renamed_handler,
        dvportgroup_destroyed_handler,
    ]
    update_handler = controllers.UpdateHandler(handlers)

    vm_synchronizer = synchronizers.VirtualMachineSynchronizer(vm_service)
    dpg_synchronizer = synchronizers.DistributedPortGroupSynchronizer(
        dpg_service
    )
    vpg_synchronizer = synchronizers.VirtualPortGroupSynchronizer(
        vm_service, vpg_service
    )
    vmi_synchronizer = synchronizers.VirtualMachineInterfaceSynchronizer(
        vm_service, vmi_service
    )
    synchronizer = synchronizers.Synchronizer(
        database,
        vm_synchronizer,
        dpg_synchronizer,
        vpg_synchronizer,
        vmi_synchronizer,
    )

    vmware_controller = controllers.VmwareController(
        synchronizer, update_handler, lock
    )
    vmware_monitor = VMwareMonitor(vmware_controller, update_set_queue)
    event_listener = EventListener(
        vmware_controller, update_set_queue, vcenter_api_client, database
    )
    supervisor = Supervisor(event_listener, vcenter_api_client)
    zookeeper_client = ZookeeperClient(
        "vcenter-fabric-manager",
        config["zookeeper"]["servers"],
        config["host_ip"],
    )
    context = {
        "lock": lock,
        "database": database,
        "vmware_monitor": vmware_monitor,
        "supervisor": supervisor,
        "zookeeper-client": zookeeper_client,
    }
    return context


def run_introspect(cfg, database, lock):
    sandesh_config = cfg["sandesh"]
    sandesh_config["collectors"] = sandesh_config["collectors"].split()
    random.shuffle(sandesh_config["collectors"])
    sandesh_config.update(
        {
            "id": Module.VCENTER_FABRIC_MANAGER,
            "hostname": socket.gethostname(),
            "table": "ObjectContrailvCenterFabricManagerNode",
            "instance_id": INSTANCE_ID_DEFAULT,
            "introspect_port": ServiceHttpPortMap[
                "contrail-vcenter-fabric-manager"
            ],
        }
    )
    sandesh_config["name"] = ModuleNames[sandesh_config["id"]]
    sandesh_config["node_type"] = Module2NodeType[sandesh_config["id"]]
    sandesh_config["node_type_name"] = NodeTypeNames[
        sandesh_config["node_type"]
    ]

    sandesh = Sandesh()
    sandesh_handler = SandeshHandler(database, lock)
    sandesh_handler.bind_handlers()
    config = SandeshConfig(http_server_ip=sandesh_config["http_server_ip"])
    sandesh.init_generator(
        module="cvfm",
        source=sandesh_config["hostname"],
        node_type=sandesh_config["node_type_name"],
        instance_id=sandesh_config["instance_id"],
        collectors=sandesh_config["collectors"],
        client_context="cvfm_context",
        http_port=sandesh_config["introspect_port"],
        sandesh_req_uve_pkg_list=["cfgm_common", "cvfm"],
        config=config,
    )
    sandesh.sandesh_logger().set_logger_params(
        logger=sandesh.logger(),
        enable_local_log=True,
        level=translate_logging_level(sandesh_config["logging_level"]),
        file=sandesh_config["log_file"],
        enable_syslog=False,
        syslog_facility=None,
    )
    ConnectionState.init(
        sandesh=sandesh,
        hostname=sandesh_config["hostname"],
        module_id=sandesh_config["name"],
        instance_id=sandesh_config["instance_id"],
        conn_status_cb=staticmethod(ConnectionState.get_conn_state_cb),
        uve_type_cls=NodeStatusUVE,
        uve_data_type_cls=NodeStatus,
        table=sandesh_config["table"],
    )


def run_vcenter_fabric_manager(supervisor, vmware_monitor):
    greenlets = [
        gevent.spawn(supervisor.supervise),
        gevent.spawn(vmware_monitor.monitor),
    ]
    gevent.joinall(greenlets, raise_error=True)


def main(args):
    cfg = load_config(args.config_file)
    context = build_context(cfg)
    vmware_monitor = context["vmware_monitor"]
    supervisor = context["supervisor"]
    database = context["database"]
    lock = context["lock"]
    run_introspect(cfg, database, lock)

    zookeeper_client = context["zookeeper-client"]
    logger = logging.getLogger("cvfm")
    logger.info("Waiting to be elected as master...")
    zookeeper_client.master_election(
        "/vcenter-fabric-manager",
        os.getpid(),
        run_vcenter_fabric_manager,
        supervisor,
        vmware_monitor,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        action="store",
        dest="config_file",
        default="/etc/contrail/contrail-vcenter-fabric-manager/config.yaml",
    )
    parsed_args = parser.parse_args()
    try:
        main(parsed_args)
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        logger = logging.getLogger("cvfm")
        logger.critical("", exc_info=True)
        raise
