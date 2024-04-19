# Python Network Config Parser Library

The purpose of this Python library is to scrape/parse device configuration and state data for interesting information.

This tool will capture and normalize unstructured data into a machine readable serialized structured data format which enables the programmatic reporting of key metrics required for detailed analysis.


## What exactly does do

Upon execution of the parsing tool, it will:
- Search for all files in the "input" folder for extensions ".zip", ".txt," and ".log" and loads each of them into memory.
- Process all candidate files through the "FileHandler".
    - If the ".zip" is detected in the name:
        - Contents for all files within each .zip file are extracted and stored in memory for further processing.
    - Contents of all non-zip candidate files detected are also stored in memory for further processing.
- Site names are derived from the filename (delineated by "-") but may be customized depending on naming convention.
- Files are checked for the following commands (based upon output requested) for data extraction via corresponding TextFSM templates:
    - "display arp" (HP Comware)
    - "display ip routing-table" (HP Comware)
    - "display mac-address" (HP Comware)
    - "show ip route" (Cisco IOS)
    - "show route" (HP Comware)
- Files are again parsed for unique characteristics of a device configuration file from which the following information is obtained on a per-device basis:
    - Device Name
    - Platform (cisco_ios, hp_comware, Juniper Junos, and checkpoint_gaia)
    - Interface IP Addresses
    - If state commands were provided (routing tables, arp_tables, mac tables, etc.)
    - IP overlap issues associated with public internet addresses registerd via [ARIN](https://www.arin.net/) against a custom dictionary in the vars/public_aggregates.json file.
    - If DHCP services are running on the device
    - If NAT is being performed on the device
- State information from previous commands are parsed using the Python "TextFSM" library to collect elements associated with the routing table, ARP table, and MAC address table of each device.
- The following report files are generated from the aggregated data for future analysis:
    - "networks_from_int.csv"
    - "networks_combined.csv
    - "route_details.csv"
    - "arp_details.csv"
    - "mac_details.csv"
    - "device_details.csv"
    - "files_missing_network_interface_addresses.csv"
    - "ipam_report.xlsx" (Aggregates data collected into a single file)

## Code Examples

### Here's an example of using the data structure to form the data structure required to facilitate an InfoBlox IPAM Import via CSV:

| Header-Network   | address*       | netmask*        | description    | enable_discovery   | discovery_member   |
|------------------|----------------|-----------------|----------------|--------------------|--------------------|
| Network          | 123.234.123.32 | 255.255.255.252 | EXAMPLEDEVICE1 | FALSE              |                    |
| Network          | 172.25.25.0    | 255.255.255.240 | EXAMPLEDEVICE1 | FALSE              |                    |
| Network          | 172.25.25.32   | 255.255.255.224 | EXAMPLEDEVICE1 | FALSE              |                    |
| Network          | 172.25.245.9   | 255.255.255.255 | EXAMPLEDEVICE1 | FALSE              |                    |

See usage examples for other potential use cases.

## Installation

This library requires Python 3.6 or above. Use the package manager [pip](https://pip.pypa.io/en/stable/) in install the package prerequisites in an isolated virtual environment environment.

```bash
pip install -r requirements.txt
mkdir input
```

## Usage

This library requires [Python 3.6 or above](https://www.python.org/). Use the package manager [pip](https://pip.pypa.io/en/stable/) in install the package prerequisites. An isolated [virtual environment (venv)](https://docs.python.org/3/library/venv.html) is highly recommended:

```python
python run_parser.py
```

### Example Output (Excel & CSV Exports)

```python
import pandas as pd
```

### Device Details

Provides for a device centric view along with unique characteristics

```python
df_device_details = pd.read_csv("device_details.csv", index_col='device')
df_device_details
```

### Network Subnets (Interfaces)
Lists network subnets for each of the network interfaces discovered in the device configuration file

```python
df_networks_from_int = pd.read_csv("networks_from_int.csv")
df_networks_from_int
```

### Network Subnets - Interfaces and Routing Tables (Combined)
Combines network subnets from the above report with subnets discovered in routing tables

```python
df_networks_combined = pd.read_csv("networks_combined.csv", index_col='device')
df_networks_combined
```

### Routing Tables

Detailed output from the device routing tables provided

```python
df_route_details = pd.read_csv("route_details.csv")
df_route_details
```

### ARP Tables

Detailed output from the device ARP tables provided

```python
df_arp_details = pd.read_csv("arp_details.csv")
df_arp_details
```

### MAC Address Tables

Detailed output from the device MAC address tables provided

```python
df_mac_details = pd.read_csv("mac_details.csv")
df_mac_details
```

### Files Missing Network Interface Configuration

List of all files that did not contain the device configuration information from which interfaces are derived

```python
df_files_missing_network_interface_addresses = pd.read_csv("files_missing_network_interface_addresses.csv")
df_files_missing_network_interface_addresses
```

## Interesting Results

### Find Poached Networks

Looks for any public IP addressable contained within the device interface

```python
int_filt = df_networks_from_int['is_private'] == False
df_networks_from_int.loc[int_filt, ['address', 'netmask', 'device', 'site','file']]
```

**See "ipam_report.xlsx" for consolidated view of the previous reports**

### Export Poached Networks to Excel (XLSX) Format

This is an example to showcase how any of the queries can be exported to Excel from this notebook for future analysis

```python
poached = df_networks_from_int.loc[int_filt, ['address', 'netmask', 'device','interface_ip', 'site']]
poached.to_excel('poached_networks.xlsx',index=False)
```

### Network Devices Providing DHCP Services (excluding firewalls)

A list of devices have local DHCP pools defined according to the device configuration

```python
dhcp_filt = df_device_details['dhcp_server'] == True
df_device_details.loc[dhcp_filt, ['site','platform', 'file']]
```

```python
df_device_details.loc[dhcp_filt,"dhcp_server"].count()
```

### Network Devices Providing NAT Services

A list of devices have NAT applied to interfaces according to the device configuration

```python
nat_filt = df_device_details['nat'] == True
df_device_details.loc[nat_filt, ['site','platform', 'file']]
```

```python
df_device_details.loc[nat_filt,'nat'].count()
```

### IP Overlap (Custom Provided Aggregate Addresses)

Leverages data pulled from aggregate addresses to determine if any of them are associated with network interfaces

```python
overlap_filt = df_networks_from_int['public_overlap'] != 'No Issue'
df_networks_from_int.loc[overlap_filt, ['address', 'netmask', 'device', 'public_overlap','public_overlap_cidr', 'site']]
```

### Export Overlapping Networks to Excel (XLSX) Format

Exports the above report to Microsoft Excel format

```python
overlap = df_networks_from_int.loc[int_filt, ['address', 'netmask', 'device', 'public_overlap', 'site']]
overlap.to_excel('public_overlap.xlsx',index=False)
```

## Authors / Contributors

[Brandon Marcum](https://brandonmarcum.net)