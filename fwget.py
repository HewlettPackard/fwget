#!/usr/bin/python3

# Copyright 2024 Hewlett Packard Enterprise Development LP
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of version 2 of the GNU General Public License as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to:
#
#  Free Software Foundation, Inc.
#  51 Franklin Street, Fifth Floor
#  Boston, MA 02110-1301, USA.

import json
import subprocess
import os
import os.path
from pprint import pprint
import sys
import re

try:
    import requests
except ImportError:
    sys.exit(
        """
Fwget requries the 'requests' Python module.
Please install it with the appropriate command as root:

                RedHat:    yum     install python3-requests
                SUSE  :    zypper  install python3-requests
                Ubuntu:    apt-get install python3-requests
                others:    pip     install requests
                                         """
    )

gen_for_old_fwpkg = [
    r"/fwpp/",
    r"/fwpp-gen8/",
    r"/fwpp-gen9/",
    r"/fwpp-gen10/",
    r"/fwpp-gen11/",
]

###########
# parse     command line, setup config file if it doens't exist, prompt for token
class Configuration:
    def __init__(self):
        self.config_file = os.path.expanduser("~") + "/.fwget.conf"
        self.username = ""
        self.password = ""
        self.ilo_address = ""
        self.token = ""
        self.sdr_url = ""
        self.default_sdr_url = "https://downloads.linux.hpe.com/SDR/repo/fwpp-gen11/current"
        
    def parse_config(self):
        if os.path.isfile(self.config_file):
            try:
                #print(self.config_file)
                with open(self.config_file, "r") as json_config_file:
                    json_config = json.load(json_config_file)
                    self.username = json_config["ilo_username"]
                    self.password = json_config["ilo_password"]
                    self.ilo_address = json_config["ilo_address"]
                    self.sdr_url = json_config["sdr_url"]
                    self.token = json_config["token"]
            except:
                print("Unable to parse " + self.config_file)
                print("Please check if the file {} exists and content is correct!".format( self.config_file))
                quit(1)
        else:
            with open(self.config_file, "w+") as config_file_handle:
                config_file_handle.write("{ \n")
                config_file_handle.write(
                    '"_comment": "For Gen9 and earlier, generate token at: http://downloads.linux.hpe.com/SDR/project/fwpp/fwget.html",  \n'
                )
                config_file_handle.write(
                    '"_comment": "Replace fwpp-gen11 with fwpp-gen10/fwpp-gen9/fwpp-gen8 as appropriate.",  \n\n'
                )
                config_file_handle.write('   "ilo_username": "na",  \n')
                config_file_handle.write('   "ilo_password": "na",  \n')
                config_file_handle.write('   "ilo_address": "na",  \n')
                config_file_handle.write('   "token": "na",  \n')
                config_file_handle.write(
                    '   "sdr_url"  : "{}"  \n\n'.format(self.default_sdr_url)
                )
                config_file_handle.write("} \n")
                config_file_handle.close()
                print(
                    """
                    A default configuration is generated.
                    Using default fwpp-gen11 firmware repository.  Please edit ~/.fwget.conf to change if needed.
                    Please edit ~/.fwget.conf to add iLO credential and re-run the utility.
                    """
                )
            quit(0)
                

class FWGet(Configuration):
    def __init__(self, args):
        super().__init__()
        self.fwget_operation = "" if len(args)<2 else args[1]
        self.fwget_keyword = "" if len(args)<3 else args[2]
        self.fwget_json_index = ""
        self.fwget_json = ".fwget.json"  # where to store sdr fw data in json format
        self.content_url = ""
        self.fwget_json_index = ""

    def parse_config(self):
        Configuration.parse_config(self)
        baseurl = self.sdr_url.replace("https://", "")
        baseurl = baseurl.replace("http://", "")
        self.index_url = (
            "https://" + self.token + ":null@" + baseurl + "/fwrepodata/fwrepo.json"
        )
        self.content_url = "https://" + self.token + ":null@" + baseurl
        self.fwget_json_index = self.gen_sdr_fw_json()
        #pprint(self.fwget_json_index)

    def gen_sdr_fw_json(self):
        index_url = self.index_url
        try:
            index = requests.get(index_url)
            if index.status_code != 200:
                raise Exception(index.status_code)
            else:
                json_index_filename = "{}/{}".format(
                    os.path.expanduser("~"), self.fwget_json
                )
                with open(json_index_filename, "w") as json_index_file:
                    json_index_file.write(index.text)
                # print("Parse firmware metadata on SDR is completed")
        except Exception as error:
            if str(error) == "404":
                print("Unable to download firmware index (404 not found):")
                print("   " + index_url)
                quit(1)
            elif str(error) == "401":
                print("Unable to download firmware index (401 not authorized).")
                print("")
                print("Token:  " + token)
                print("")
                print(
                    "A valid warranty or support contract is required to access HPE firmware."
                )
                print(
                    "Please visit http://downloads.linux.hpe.com/SDR/project/fwpp-postprod to "
                )
                print("generate an access token then add it to ~/.fwget.conf.")
                quit(1)
            else:
                print("Unable to download")
                print("   " + index_url)
                print("   to ~/fwrepo.json")
                print(str(error))
                quit(1)

        try:
            json_index_filename = "{}/{}".format(
                os.path.expanduser("~"), self.fwget_json
            )
            # print(json_index_filename)
            with open(json_index_filename, "r") as json_index_file:
                self.json_index = json.load(json_index_file)
                # print("load json index file is completed")
        except:
            print("Unable to open cached copy of index ~/.fwget.json")
            quit(1)
        return self.json_index

    def search(self, searchstring, json_index):
        """
        search substring search in filename and description, secretly sort output by date
        """
        output_list = []
        for fw in json_index:
            if searchstring.lower() in fw.lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["description"].lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["target"]:
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["deviceclass"].lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
        output_list_sorted_by_date = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for tuple in output_list_sorted_by_date:
            print(
                str(tuple[1]).ljust(66)
                + "   "
                + tuple[2].encode("ascii", "ignore").decode()
            )  # unicode, works in python2&3
        return 0

    def locate(self, searchstring, json_index, content_url):
        """
        locate substring search in filename and description, output urls secretly sorted by date
        """
        output_list = []
        for fw in json_index:
            if searchstring.lower() in fw.lower():
                output_list.append(
                    (json_index[fw]["date"], fw, json_index[fw]["description"])
                )
            elif searchstring.lower() in json_index[fw]["description"].lower():
                output_list.append(
                    (json_index[fw]["date"], fw, json_index[fw]["description"])
                )
        output_list_sorted_by_date = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for tuple in output_list_sorted_by_date:
            print(content_url + "/" + tuple[1])
        return 0

    ##########
    # download download file supplied on command name, no wildcards
    def download(self, file, content_url):
        url = content_url + "/" + file
        print(f"download {file} ...")
        try:
            html_request = requests.get(url)
            if html_request.status_code != 200:
                raise Exception(html_request.status_code)
            else:
                with open(file, "wb") as firmware_file:
                    firmware_file.write(html_request.content)
        except Exception as error:
            if str(error) == "404":
                print("Unable to download firmware (404 not found):")
                print("   " + url)
                quit(1)
            elif str(error) == "401":
                print("""
                    Unable to download firmware (401 not authorized)
                    A valid warranty or support contract is required to access HPE firmware."
                    Please visit http://downloads.linux.hpe.com/SDR/project/fwpp/ to "
                    generate an access token then add it to ~/.fwget.conf. 
                """)
                quit(1)
            else:
                print("Unable to download.")
                print(str(error))
                quit(1)

        # Download the decoupled JSON file corresponding to fwpkg, introduced starting from Gen12 SPP
        if file.endswith(".fwpkg") and not any(re.search(gen, url) for gen in gen_for_old_fwpkg):
            json_file = file.replace('.fwpkg', '.json')
            url = content_url + "/" + json_file
            try:
                html_request = requests.get(url)
                if html_request.status_code != 200:
                   raise Exception(html_request.status_code)
                else:
                    print(f"download {json_file} ...")
                    with open(json_file, 'wb') as json_file:
                         json_file.write(html_request.content)
            except Exception as error:
                if str(error) == '404':
                   quit(1)
                elif str(error) == '401':
                   print("Unable to download JSON file (401 not authorized).")
                   quit(1)
                else:
                   print("Unable to download.")
                   print(str(error))
                   quit(1)

        return 0

    ##########
    # list     everything, sorted by filename
    def list(self, json_index):
        output_list = []
        for fw in json_index:
            # print (fw.ljust(33) + " " +  json_index[fw]["description"])
            output_list.append((fw, json_index[fw]["description"]))
        output_list_sorted_by_filename = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for tuple in output_list_sorted_by_filename:
            # print (tuple[0].encode('ascii','ignore').ljust(33).decode() + "   " + tuple[1].encode('ascii','ignore').decode() ) # unicode, works in python2&3
            print(
                str(tuple[0]).ljust(33)
                + "   "
                + tuple[1].encode("ascii", "ignore").decode()
            )  # unicode, works in python2&3
        return 0

    def help_menu(self):
        msg = """
        Usage: fwget {locate,search,download,list} keyword

        fwget to pull firmware from HPE Software Delivery Repository
        positional arguments:
            {locate,search,download,list}
                search firmware for server models e.g., search dl379
                download firmware based on search result e.g., download U30_2.10_05_21_2019.fwpkg
                list all firmwares on HPE SDR e.g., list
                locate correspodant URL of the given firmware package e.g., locate U30_2.10_05_21_2019.fwpkg
                
            keyword
                keyword for fwget operations
        
        options:
            -h, --help      show this help message and exit
        """
        print(msg)

    def operation_handler(self):
        if self.fwget_operation == "search" and self.fwget_keyword != None:
            self.search(self.fwget_keyword, self.fwget_json_index)
        elif self.fwget_operation == "locate" and self.fwget_keyword != None:
            self.locate(self.fwget_keyword, self.fwget_json_index, self.content_url)
        elif self.fwget_operation == "download" and self.fwget_keyword != None:
            self.download(self.fwget_keyword, self.content_url)
        elif self.fwget_operation == "list":
            self.list(self.fwget_json_index)
        else:
            raise KeyError(
                "{} operation is incorrect! Please use -h or --help for more usage".format(
                    self.fwget_operation
                )
            )
###########

# output = subprocess.check_output(["ilorest --nologo rawget /redfish/v1/UpdateService/FirmwareInventory/ --expand  -u accname  -p pass"], shell=True)
# cmd="curl -s --insecure  -u acc:pass -X GET https://192.168.100.107/redfish/v1/UpdateService/FirmwareInventory/ | jq . | tee system_info.json"
# output = subprocess.check_output(cmd)

class FWList(Configuration):
    def __init__(self,args):
        Configuration.__init__(self)
        self.fwlist_odataid_output_format= "spaced_display" if len(args)<2 else args[1]
        #print(len(args),args,args[1])
        self.odataid_file = os.path.expanduser("~") + "/.fwlist.output"  # where to store odataid in json format
        self.firmware_inventory_url = "/redfish/v1/UpdateService/FirmwareInventory/"

    def help_menu(self):
        msg = """
        Usage: fwlist {spaced_display,json_display}

        positional arguments:
            {spaced_display,json_display}
                output data in spaced or json format

        fwlist to discover and export the local server firmware information. 
        The firmware information contains target ID, and that can be used as key for fwget for firmware search and download. 

        options:
            -h, --help      show this help message and exit
        """
        print(msg)

    def gen_odataid_parse_cmd(self, odataid: list) -> None:
        target_url = "{}".format(odataid)
        cmd = "sudo ilorest rawget --nologo {} --url {} -u {} -p {}".format(
            target_url, self.ilo_address, self.username, self.password
        )
        return cmd

    def gen_firmware_parse_cmd(self):
        target_url = self.firmware_inventory_url
        cmd = "sudo ilorest rawget --nologo {} --url {} -u {} -p {}".format(
            target_url, self.ilo_address, self.username, self.password
        )
        return cmd

    def odata_parse(self, odata_id_list: list) -> None:
        """
        parse odata based on odataid url

        [{'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/1/',
          'Description': 'SystemBMC',
          'Name': 'iLO 5',
          'Version': '3.03 Mar 22 2024',
          'targets': ['4764a662-b342-4fc7-9ce9-258c5d99e815',
                      'c0bcf2b9-1141-49af-aab8-c73791f0349c']},
        {'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/20/',
          'Description': 'SanDisk SSD PLUS 120GB',
          'Name': '120GB 6G SATA SSD',
          'Version': 'UE5100RL',
          'targets': ['532340a5-6e61-6944-736b-20534a87fef4']}]
        """

        cmd_list = [self.gen_odataid_parse_cmd(odataid) for odataid in odata_id_list]
        subprocess.run(
            cmd_list[0],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            timeout=60,
        )
        results = [
            subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
            )
            for cmd in cmd_list
        ]
        fw_info_list = [json.loads(ret.stdout) for ret in results]
        odata_list = []
        for fw_info in fw_info_list:
            try:
                odata = {}
                odata["@odata.id"] = fw_info["@odata.id"]
                odata["Version"] = fw_info["Version"]
                odata["Description"] = fw_info["Description"]
                odata["Name"] = fw_info["Name"]
                # print(fw_info["Oem"]["Hpe"].keys())
                if "Targets" in fw_info["Oem"]["Hpe"].keys():
                    odata["targets"] = [
                        target for target in fw_info["Oem"]["Hpe"]["Targets"]
                    ]
                odata_list.append(odata)
            except:
                print("odataid parse error {}", sys.stderr)
                exit(1)
        return odata_list

    def firmware_parse(self):
        """
        parse firmware via iLO restful API and output in a odataid list
        """
        cmd = self.gen_firmware_parse_cmd()
        #print(cmd)
        # ret = subprocess.run(shlex.split(cmd), stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell=True)
        ret = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, timeout=60
        )
        try:
            fw_list = json.loads(ret.stdout)
        except:
            print("firmware parse error {}", sys.stderr)
            print("Please check if iLO credential is correct and network connection is good")
            exit(1)

        odata_id_list = [odataid["@odata.id"] for odataid in fw_list["Members"]]
        odata_list = self.odata_parse(odata_id_list)
        return odata_list

    def odataid_export(self, odata_list: list, fwlist_odataid_output_format="spaced_display") -> None:
        """
        write json to file with human-friendly formatting
        """

        def odataid_export_in_space(odata_list: list) -> None:
            output_context=""
            for odata in odata_list:
                for attribute, value in odata.items():
                    if type(value) is list:
                        output_str=" ".join(value)
                        output_context+="\n{}:{}".format(attribute,output_str)
                    else:
                        output_context+="\n{}:{}".format(attribute,value)
                output_context+="\n"

            print(output_context)
            with open(self.odataid_file, "w") as f:
                print("export result to ", self.odataid_file)
                f.write(output_context)

        def odataid_export_in_json(odata_list: list) -> None:
            pprint(odata_list) 
            with open(self.odataid_file, "w") as f:
                print("export result to ", self.odataid_file)
                json.dump(odata_list, f, indent=4, sort_keys=True)

        odataid_display_dict={
                "spaced_display":odataid_export_in_space,
                "json_display":odataid_export_in_json }

        try: 
            odataid_display_dict[fwlist_odataid_output_format](odata_list)
        except:
            print("Output error in odataid_export!")
            print("Supported display:{}, Selected display:{}".format( odataid_display_dict.keys(), fwlist_odataid_output_format="spaced_display"))
            exit(1)

def do_fwget(arglist):
    fwget = FWGet(arglist)
    fwget.parse_config()
    if argcount >1:
        if arglist[1] == "-h" or arglist[1] == "--help":
            fwget.help_menu()
        else:
            fwget.operation_handler()
    else:
        print("Unrecongnized command, please use fwget -h for more info\n")
        exit(0)

def do_fwlist(arglist):
    fwlist = FWList(arglist)
    fwlist.parse_config()
    if argcount > 1 and (sys.argv[1] == "-h" or sys.argv[1] == "--help"):
        fwlist.help_menu()
        exit(0)

    elif argcount >= 1 and sys.argv[0].endswith("fwlist"):
        odata_list = fwlist.firmware_parse()
        fwlist.odataid_export(odata_list,fwlist.fwlist_odataid_output_format)
    else:
        print("Unrecongnized command, please use fwlist -h for more info\n")
        exit(0)

if __name__ == "__main__":
    arglist = sys.argv
    argcount = len(sys.argv)
    #print(argcount,arglist)
    if "fwget" in sys.argv[0]:
        do_fwget(sys.argv)
    elif "fwlist" in sys.argv[0]:
        do_fwlist(sys.argv)
