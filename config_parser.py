import ipaddress
import re
from zipfile import ZipFile
from ntc_templates.parse import parse_output
from rich import print


class FileHandler:
    """This class is responsible for file handling functions such as loading and unzipping"""

    def __init__(self, input_file) -> None:
        print(f"\nLoading {input_file}...\n")
        if ".zip" in input_file.lower():
            self.input_file = ZipFile(input_file)
            self.name = {
                name: self.input_file.read(name)
                for name in self.input_file.namelist()
                if name[-1] != "/"
            }
        else:
            try:
                with open(input_file) as self.f:
                    self.name = {input_file: self.f.read()}
            except Exception as e:
                print("Ouch!", e.__class__, "occurred.")

    def __str__(self):
        return self.name


class CommandSlicer:
    """Takes in file output, searches for device commands, and slices them accordingly"""

    def __init__(self, orig_file, ref_file, site, output, command_list) -> None:
        if ".zip".lower() in orig_file:
            self.ref_file = f"{orig_file[6:]}/{ref_file}"
        else:
            self.ref_file = ref_file[6:]

        self.site = site

        self_command_regex_dict = {}

        for self.command in command_list:
            self.command_minimized = []
            for self.command_word in self.command.split():
                self.command_minimized.append(self.command_word[:2] + r"[\w-]*\s*")
            self_command_regex_dict[self.command] = " ".join(self.command_minimized)

        self.hostname_regex = r"^.*[@<\s](?!command)([\w-]*)[#>].*"
        self.commands_found = {}

        for self.command, self.command_regex in self_command_regex_dict.items():
            self.regex_combined = f"{self.hostname_regex}({self.command_regex})"
            self.match_command_output = re.search(
                self.regex_combined, output, flags=re.MULTILINE
            )
            if self.match_command_output is not None:
                self.command_hostname = self.match_command_output.group(1)
                for self.index, self.line in enumerate(output.split("\n")):
                    if re.search(self.regex_combined, self.line):
                        self.top_sliced_output = output.split("\n")[self.index + 1 :]
                        break
                    else:
                        self.top_sliced_output = output.split("\n")
                self.sliced_command_list = []
                for self.index, self.line in enumerate(self.top_sliced_output):
                    if not re.search(self.hostname_regex, self.line):
                        self.sliced_command_list.append(self.line)
                    else:
                        break
                self.sliced_command_output = "\n".join(self.sliced_command_list)
                self.commands_found[self.command] = str(self.sliced_command_output)


class DeviceConfigParser:
    """Represents network device and associated attributes"""

    def __init__(self, orig_file, ref_file, site, output, **command_contents) -> None:
        if ".zip".lower() in orig_file:
            self.ref_file = f"{orig_file[6:]}/{ref_file}"
        else:
            self.ref_file = ref_file[6:]
        self.site = site
        self.routes = []
        self.arp = []
        self.macs = []

        # Parse Device Name from Device Configuration
        self.match_name_checkpoint_gaia = re.search(r"set hostname ([\w-]*)", output)
        # Juniper hostname identification can vary depending on failover policy
        self.match_name_juniper_junos = re.search(r"system host-name ([\w-]*)", output)
        self.match_name_hp_comware = re.search(r"sysname ([\w-]*)", output)
        self.match_name_cisco_ios = re.search(r"hostname ([\w-]*)", output)

        if self.match_name_checkpoint_gaia is not None:
            self.name = str(self.match_name_checkpoint_gaia.group(1))
            self.missing_hostname = False
            self.platform = "checkpoint_gaia"
        elif self.match_name_juniper_junos is not None:
            self.name = str(self.match_name_juniper_junos.group(1))
            self.missing_hostname = False
            self.platform = "juniper_junos"
        elif self.match_name_hp_comware is not None:
            self.name = str(self.match_name_hp_comware.group(1))
            self.missing_hostname = False
            self.platform = "hp_comware"
        elif self.match_name_cisco_ios is not None:
            self.name = str(self.match_name_cisco_ios.group(1))
            self.missing_hostname = False
            self.platform = "cisco_ios"
        else:
            self.match_name_unknown = re.search(
                r"^.*[@<\s](?!command)(\w*)[#>].*", output, flags=re.MULTILINE
            )
            if self.match_name_unknown is not None:
                self.name = str(self.match_name_unknown.group(1))
                self.missing_hostname = False
                # Defaults to checkpoint for command parsing
                self.platform = "checkpoint_gaia"
            else:
                self.name = "No hostname was detected"
                self.missing_hostname = True
                self.platform = "No platform detected"

        # Parse Interface Addresses from Device Configuration
        if self.platform == "checkpoint_gaia":
            self.match_int_addresses = re.findall(
                r"ipv4-address (25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?) mask-length (\d+)",
                output,
            )
        elif self.platform == "juniper_junos":
            self.match_int_addresses = re.findall(
                r"inet address (25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/(\d+)",
                output,
            )
        else:
            self.match_int_addresses = re.findall(
                r"ip address (25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?) (255)\.(0|128|192|224|240|248|252|254|255)\.(0|128|192|224|240|248|252|254|255)\.(0|128|192|224|240|248|252|254|255)",
                output,
            )

        self.int_addresses = []
        if self.match_int_addresses is not None:
            self.missing_networks = False
            if self.platform == "checkpoint_gaia" or self.platform == "juniper_junos":
                for self.int_address in self.match_int_addresses:
                    self.int_addresses.append(
                        ipaddress.ip_interface(
                            f"{self.int_address[0]}.{self.int_address[1]}.{self.int_address[2]}.{self.int_address[3]}/{self.int_address[4]}"
                        )
                    )
            else:
                for self.int_address in self.match_int_addresses:
                    self.int_addresses.append(
                        ipaddress.ip_interface(
                            f"{self.int_address[0]}.{self.int_address[1]}.{self.int_address[2]}.{self.int_address[3]}/{self.int_address[4]}.{self.int_address[5]}.{self.int_address[6]}.{self.int_address[7]}"
                        )
                    )
        if not self.int_addresses:
            self.missing_networks = True

        # Determine if device is running a DHCP Server
        if re.findall(r"dhcp pool|dhcp server ip-pool", output):
            self.dhcp_server = True
        else:
            self.dhcp_server = False

        # Determine if device has NAT configuration
        if re.findall(
            r"nat static|nat outbound|ip nat inside|ip nat outside|set nat-pool|set source pool|set destination pool|set static rule-set",
            output,
        ):
            self.nat = True
        else:
            self.nat = False

        # Parse commands via NTC Templates
        if command_contents.get(self.name):
            print(
                f"Found the following commands to parse:\n{command_contents.get(self.name).keys()}"
            )
            for self.command, self.command_content in command_contents.get(
                self.name
            ).items():
                self.lines = self.command_content.split("\n")
                self.remove_lines = []
                for self.index, self.row in enumerate(self.lines):
                    if "proprietary" in self.row.lower():
                        self.remove_lines.append(self.index)
                for self.index in sorted(self.remove_lines, reverse=True):
                    del self.lines[self.index]
                self.data = "".join(self.lines)
                try:
                    template_parsed = parse_output(
                        platform=self.platform, command=self.command, data=self.data
                    )
                    if "arp" in self.command:
                        self.arp = template_parsed
                    if "rout" in self.command:
                        self.routes = template_parsed
                    if "mac" in self.command:
                        self.macs = template_parsed
                    print(
                        f'\n"[bold green]{self.command}" successfully parsed:[/]\n{template_parsed}'
                    )
                except Exception as e:
                    print(
                        f"[bold yellow]TextFSM could not parse[/] {self.command} from {self.ref_file} \n\n{e}"
                    )

    def __str__(self):
        return self.name

    @property
    def sorted_int_addresses(self):
        return sorted(self.int_addresses)

    @property
    def route_networks(self):
        self.route_ip_networks = []
        if self.routes:
            for self.network in self.routes:
                try:
                    self.route_ip_networks.append(
                        ipaddress.IPv4Network(
                            f"{self.network.get('network')}/{self.network.get('mask')}"
                        )
                    )
                except Exception as e:
                    print(
                        f"[bold yellow]Unable to add network from {self.ref_file} (likely incomplete data)\n\n{e}"
                    )
        return sorted(self.route_ip_networks)
