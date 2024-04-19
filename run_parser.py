import re
import ipaddress
import pandas as pd
import json
from sys import exit, platform
from csv import DictWriter, writer
from tabulate import tabulate
from config_parser import DeviceConfigParser
from config_parser import FileHandler
from config_parser import CommandSlicer
from glob import glob
from operator import itemgetter
from rich import print
from constants import FILE_TYPES, COMMAND_LIST

# Load public aggregates data and convert to IP Objects
try:
    with open("vars/public_aggregates.json") as f:
        public_aggregates = json.load(f)
except Exception as e:
    print(
        f"[bold red]Failed to load aggregate classification from public_aggregates.json"
    )
    print("[bold red]Error Details: ", e.__class__)

# Function to generate reports
def csv_export(file_name, report_dict, friendly_description):
    try:
        with open(file_name, "w", newline="") as csvfile:
            writer = DictWriter(csvfile, fieldnames=report_dict[0].keys())
            writer.writeheader()
            for report_row in report_dict:
                writer.writerow(report_row)
        print(f'\n[bold green]File "{file_name}" has been successfully created\n')
    except Exception as e:
        print("Ouch!", e.__class__, "occurred.")
    # Print Output to Console in Table Format
    if report_dict:
        print(f"\n[bold red]{friendly_description}:\n")
        print(tabulate(report_dict, headers="keys", tablefmt="github"))
        print("\n" * 2)
    else:
        print(f"[bold red]No {friendly_description} found!")


# Search directory for relevant file types
files_found = []  # List of dictionaries
for file_type in FILE_TYPES:
    files_found.extend(glob(file_type))

# Primary Data Models
sites = []  # List
devices = []  # List of Device Objects.
"""
Example Device Search:
next((device for device in devices if device["name"] == "ROUTER1"), False)
"""

# Dict device_name: Dict of lists containing dict of keys("command_found","sliced_command_output")
command_contents = {}

files_missing_device_name = []  # List of strings
files_missing_site_name = []  # List of strings
files_missing_network_interface_addresses = []  # List of dictionaries
# TODO TextFSM_parsing_errors = []  # List of dictionaries

# Gather data from files
if files_found:
    for orig_file in files_found:
        # Parse site name from filename
        match_site_name = re.search(r".*\/(.*) -", orig_file)
        if match_site_name is not None:
            site_name = match_site_name.group(1)
            sites.append(site_name)
        else:
            site_name = ""
            files_missing_site_name.append(orig_file[6:])
        contents = FileHandler(orig_file)
        # Searches every file for commands that we intend to parse
        for ref_file, content in contents.name.items():
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            commands_sliced = CommandSlicer(
                orig_file, ref_file, site_name, content, COMMAND_LIST
            )
            if commands_sliced.commands_found:
                command_contents[
                    commands_sliced.command_hostname
                ] = commands_sliced.commands_found
        # Populate devices data model based on running config
        for ref_file, content in contents.name.items():
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            device = DeviceConfigParser(
                orig_file, ref_file, site_name, content, **command_contents
            )
            devices.append(device)
else:
    print(f"[bold red] No Files Found for the Following Paths: {FILE_TYPES}")
    exit(1)


# Data Models
device_details = []  # List of dictionaries
interface_ips = []  # List of dictionaries
route_networks = []  # List of dictionaries
route_details = []  # List of dictionaries
arp_details = []  # List of dictionaries
mac_details = []  # List of dictionaries

# Reports
network_report_interfaces = []  # List of dictionaries
networks_combined = []  # List of dictionaries

# Evaluate each device to capture data models
for device in devices:
    if device.missing_hostname:
        files_missing_device_name.append(device.ref_file)
    if device.missing_networks:
        files_missing_network_interface_addresses.append(
            {"Device Name": device.name, "File Name": device.ref_file}
        )
    # Populate device report if config is valid
    if device.missing_hostname == False and device.missing_networks == False:
        device_dict = {}
        device_dict["device"] = device.name
        device_dict["platform"] = device.platform
        device_dict["routing_table"] = True if device.routes else False
        device_dict["arp_table"] = True if device.arp else False
        device_dict["mac_table"] = True if device.macs else False
        device_dict["dhcp_server"] = device.dhcp_server
        device_dict["nat"] = device.nat
        device_dict["site"] = device.site
        device_dict["file"] = device.ref_file
        device_details.append(device_dict)
    # Populate interfaces data model
    for interface in device.sorted_int_addresses:
        interface_dict = {}
        interface_dict["int_address"] = interface
        interface_dict["ip_network"] = interface.network
        interface_dict["device"] = device.name
        interface_dict["site"] = device.site
        interface_dict["file"] = device.ref_file
        interface_dict["platform"] = device.platform
        interface_dict["source"] = "interface"
        if public_aggregates and interface.network.with_prefixlen != "0.0.0.0/0":
            interface_dict["public_overlap"] = "No Issue"
            interface_dict["public_overlap_cidr"] = ""
            route_aggregate_found = False
            for category in public_aggregates.keys():
                for aggregate in public_aggregates[category]:
                    if interface.network.overlaps(ipaddress.ip_network(aggregate)):
                        interface_dict["public_overlap"] = category
                        interface_dict["public_overlap_cidr"] = aggregate
                        break
                if route_aggregate_found:
                    break
        else:
            interface_dict["public_overlap"] = "No Issue"
            interface_dict["public_overlap_cidr"] = ""
        interface_ips.append(interface_dict)
    # Populate routes data model
    for route in device.route_networks:
        routes_dict = {}
        routes_dict["ip_network"] = route
        routes_dict["device"] = device.name
        routes_dict["site"] = device.site
        routes_dict["file"] = device.ref_file
        routes_dict["platform"] = device.platform
        routes_dict["source"] = "routing_table"
        if public_aggregates and route.with_prefixlen != "0.0.0.0/0":
            routes_dict["public_overlap"] = "No Issue"
            routes_dict["public_overlap_cidr"] = ""
            public_aggregate_found = False
            for category in public_aggregates.keys():
                for aggregate in public_aggregates[category]:
                    if route.overlaps(ipaddress.ip_network(aggregate)):
                        routes_dict["public_overlap"] = category
                        routes_dict["public_overlap_cidr"] = aggregate
                        break
                if public_aggregate_found:
                    break
        else:
            routes_dict["public_overlap"] = "No Issue"
            routes_dict["public_overlap_cidr"] = ""
        route_networks.append(routes_dict)
    # Populate route details data model
    if device.routes:
        for route_detail in device.routes:
            route_details_dict = {}
            if device.platform == "hp_comware":
                route_details_dict["protocol"] = route_detail["protocal"]
                route_details_dict["network"] = route_detail.get("network")
                route_details_dict["mask"] = route_detail.get("mask")
                route_details_dict["nexthop_ip"] = route_detail.get("nexthop_ip")
            if device.platform == "cisco_ios":
                route_details_dict["protocol"] = route_detail.get("protocol")
                route_details_dict["network"] = route_detail.get("network")
                route_details_dict["mask"] = route_detail.get("mask")
                route_details_dict["nexthop_ip"] = route_detail.get("nexthop_ip")
            if device.platform == "checkpoint_gaia":
                route_details_dict["protocol"] = route_detail["protocol"]
                route_details_dict["network"] = route_detail.get("network")
                route_details_dict["mask"] = route_detail.get("mask")
                route_details_dict["nexthop_ip"] = route_detail.get("nexthopip")
            route_details_dict["device"] = device.name
            route_details_dict["platform"] = device.platform
            route_details_dict["source"] = "routing_table"
            route_details_dict["site"] = device.site
            route_details_dict["file"] = device.ref_file
            route_details.append(route_details_dict)
    # Populate arp data model
    if device.arp:
        for arp in device.arp:
            arp_dict = {**arp}
            arp_dict["device"] = device.name
            arp_dict["platform"] = device.platform
            arp_dict["source"] = "arp_table"
            arp_dict["site"] = device.site
            arp_dict["file"] = device.ref_file
            arp_details.append(arp_dict)
    # Populate macs data model
    if device.macs:
        for mac in device.macs:
            mac_dict = {**mac}
            mac_dict["device"] = device.name
            mac_dict["platform"] = device.platform
            mac_dict["source"] = "mac_table"
            mac_dict["site"] = device.site
            mac_dict["file"] = device.ref_file
            mac_details.append(mac_dict)

# Populate data structure for network interfaces report
for network in sorted(interface_ips, key=itemgetter("int_address")):
    int_network_dict = {}
    int_network_dict["Header-Network"] = "Network"
    int_network_dict["address"] = network[
        "int_address"
    ].network.network_address.exploded
    int_network_dict["netmask"] = network["int_address"].netmask.exploded
    int_network_dict["description"] = ""
    int_network_dict["device"] = network["device"]
    int_network_dict["interface_ip"] = network["int_address"].compressed
    int_network_dict["platform"] = network["platform"]
    int_network_dict["site"] = network["site"]
    int_network_dict["public_overlap"] = network.get("public_overlap")
    int_network_dict["public_overlap_cidr"] = network.get("public_overlap_cidr")
    int_network_dict["is_private"] = network["int_address"].network.is_private
    int_network_dict["is_loopback"] = network["int_address"].network.is_loopback
    int_network_dict["is_reserved"] = network["int_address"].network.is_reserved
    int_network_dict["file"] = network["file"]
    network_report_interfaces.append(int_network_dict)


# Open XLSX File for Exporting
xlsx_writer = pd.ExcelWriter("ipam_report.xlsx")

# Export Networks (Interfaces) to CSV in InfoBlox Format and Print to Console
csv_export("networks_from_int.csv", network_report_interfaces, "Networks Found")
pd_network_report_interfaces = pd.DataFrame(network_report_interfaces)
pd_network_report_interfaces.to_excel(
    xlsx_writer,
    sheet_name="Network Subnets - Interfaces",
    index=False,
    freeze_panes=(1, 0),
)


# Combine the interface and routing data models for consolidated report (all networks)
networks_combined_list = [*interface_ips, *route_networks]

# Populate data structure for all networks report
for network in sorted(networks_combined_list, key=itemgetter("ip_network")):
    all_network_dict = {}
    all_network_dict["Header-Network"] = "Network"
    all_network_dict["address"] = network["ip_network"].network_address.exploded
    all_network_dict["netmask"] = network["ip_network"].netmask.exploded
    all_network_dict["description"] = ""
    all_network_dict["device"] = network["device"]
    all_network_dict["source"] = network["source"]
    all_network_dict["platform"] = network["platform"]
    all_network_dict["site"] = network["site"]
    all_network_dict["public_overlap"] = network.get("public_overlap")
    all_network_dict["public_overlap_cidr"] = network.get("public_overlap_cidr")
    all_network_dict["is_private"] = network["ip_network"].is_private
    all_network_dict["is_loopback"] = network["ip_network"].is_loopback
    all_network_dict["is_reserved"] = network["ip_network"].is_reserved
    all_network_dict["file"] = network["file"]
    networks_combined.append(all_network_dict)


# Export Networks to CSV in InfoBlox Format and Print to Console
csv_export("networks_combined.csv", networks_combined, "Networks Found")
pd_networks_combined = pd.DataFrame(networks_combined)
pd_networks_combined.to_excel(
    xlsx_writer,
    sheet_name="Network Subnets - All",
    index=False,
    freeze_panes=(1, 0),
)

# Export Route Details to CSV in InfoBlox Format and Print to Console
csv_export("route_details.csv", route_details, "Route Details")
pd_route_details = pd.DataFrame(route_details)
pd_route_details.to_excel(
    xlsx_writer,
    sheet_name="Routing Tables",
    index=False,
    freeze_panes=(1, 0),
)

# Export ARP Details to CSV in InfoBlox Format and Print to Console
csv_export(
    "arp_details.csv",
    sorted(arp_details, key=lambda ip: (ipaddress.ip_address(ip["ipaddress"]))),
    "ARP Addresses",
)
pd_arp_details = pd.DataFrame(
    sorted(arp_details, key=lambda ip: (ipaddress.ip_address(ip["ipaddress"])))
)
pd_arp_details.to_excel(
    xlsx_writer,
    sheet_name="ARP Tables",
    index=False,
    freeze_panes=(1, 0),
)

# Export MAC Details to CSV in InfoBlox Format and Print to Console
csv_export("mac_details.csv", mac_details, "MAC Addresses")
pd_mac_details = pd.DataFrame(mac_details)
pd_mac_details.to_excel(
    xlsx_writer,
    sheet_name="Mac Tables",
    index=False,
    freeze_panes=(1, 0),
)

# Export Device Details to CSV in InfoBlox Format and Print to Console
csv_export("device_details.csv", device_details, "Device Details")
pd_device_details = pd.DataFrame(device_details)
pd_device_details.to_excel(
    xlsx_writer,
    sheet_name="Device Details",
    index=False,
    freeze_panes=(1, 0),
)


csv_export(
    "files_missing_network_interface_addresses.csv",
    files_missing_network_interface_addresses,
    "Device configuration is either missing, redacted, or no interface IP addressing was contained within the following files",
)
pd_files_missing_network_interface_addresses = pd.DataFrame(
    files_missing_network_interface_addresses
)
pd_files_missing_network_interface_addresses.to_excel(
    xlsx_writer,
    sheet_name="Missing Interface Addresses",
    index=False,
    freeze_panes=(1, 0),
)

xlsx_writer.close()

# Print list of files missing site names
if files_missing_site_name:
    print("\n[bold red]No site names were found for the following files:\n")
    for ref_file in files_missing_site_name:
        print(f"{ref_file}")
    print("\n\n")

# Print files missing a device name (Goal is 0)
if files_missing_device_name:
    print("\n[bold red]No hostname could be identified for the following files:\n")
    for ref_file in files_missing_device_name:
        print(f"{ref_file}")
    print("\n\n")
