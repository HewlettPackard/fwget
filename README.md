# Introduction
HPE [fwget](https://downloads.linux.hpe.com/SDR/project/fwpp/fwget.html) is a simple command-line browser that interacts with the HPE Firmware Pack for ProLiant online repository. This Python3 script provides the following two commands:

1. fwget provides search, locate, and download firmware packages, including rpm and fwpkg files. Acquired firmware may then be flashed with the fwget companion tool "ilorest", or by running the embedded setup command found in firmware rpms. If you know how to use apt-get, or yum, you know how to use fwget.

2. fwlist to discover and export the local server firmware information. The firmware information contains the target ID, which can be used as a key for fwget for firmware search and download.


NOTE:
1. For ProLiant Gen9, Gen8 and G7 servers, you must additionally have an active warranty or support contract linked to your HPE Passport account to access HPE firmware updates. To access Gen9 and earlier firmware repositories, generate your token here. and place it in ~/.fwget.conf after running fwget for the first time.

2. fwlist needs "iLOrest" support, which is available for Gen9 servers and later.

3. Please manually remove ~/.fwget.conf when upgrading if you have a previously installed fwget version earlier than 1.0.4.

4. The fwget v1.0.4 automatically generates a new .fwget.conf at the first running time as shown below, which the user needs to update with the server iLO configuration. Configure the ~/.fwget.conf file.


The example below is configured for Gen 11 server firmware repository.
{
   "ilo_address": "10.22.26.201",
   "ilo_username": "account_example",
   "ilo_password": "Password_example",
   "ilo_proxy": "no",
    "token": "na",
    "sdr_url" : "https://downloads.linux.hpe.com/SDR/repo/fwpp-gen11/current"
}

# Usage

* $ fwget < search | locate | download | list > [ search term ]

* $ fwlist < spaced_display | json_display >

## Examples

### fwget

*$ fwget search dl380*            [what's my ProLiant model?](http://downloads.linux.hpe.com/SDR/gen.html)

    U70_1.20_01_17_2025.fwpkg      ROM Flash Firmware Package - System ROM for HPE ProLiant Compute DL380a Gen12 (U70)
    U68_1.20_02_14_2025.fwpkg      ROM Flash Firmware Package - HPE ProLiant Compute DL360/DL380/ML350 Gen12 Servers (U68) Servers
    U72_1.20_02_14_2025.fwpkg      ROM Flash Firmware Package - System ROM for HPE ProLiant Compute DL380a Gen12 (U72)

*$ fwget download U70_1.20_01_17_2025.fwpkg* 

    download U70_1.20_01_17_2025.fwpkg ...
    download U70_1.20_01_17_2025.json ...


*$ ilorest flashfwpkg U30_2.10_05_21_2019.fwpkg* 

    iLOrest : RESTful Interface Tool version 3.0
    Copyright (c) 2014, 2019 Hewlett Packard Enterprise Development LP
    -------------------------------------------------------------------------------------------------
    Uploading firmware: U30_2.10_05_21_2019.signed.flash
    Uploading component U30_2.10_05_21_2019.signed.flash
    Component U30_2.10_05_21_2019.signed.flash uploaded successfully
    0 hour(s) 1 minute(s) 26 second(s)
    Firmware has been successfully flashed, and a reboot is required for this firmware to take effect.

### fwlist

*$ fwlist spaced_display* 

    @odata.id:/redfish/v1/UpdateService/FirmwareInventory/1/
    Version:1.62 Jul 31 2024
    Description:SystemBMC
    Name:iLO 6
    targets:e6d3c844-14a6-4f1f-84a3-c06013910306

    @odata.id:/redfish/v1/UpdateService/FirmwareInventory/2/
    Version:A55 v2.10 (09/19/2024)
    Description:SystemRomActive
    Name:System ROM
    targets:00000000-0000-0000-0000-000000000243 00000000-0000-0000-0000-000001413535 00000000-0000-0000-0001-000000010243 00000000-0000-0000-0001-000000020243
    
*$ fwlist json_display*

    [{'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/1/',
      'Description': 'SystemBMC',
      'Name': 'iLO 6',
      'Version': '1.62 Jul 31 2024',
      'targets': ['e6d3c844-14a6-4f1f-84a3-c06013910306']},
     {'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/2/',
      'Description': 'SystemRomActive',
      'Name': 'System ROM',
      'Version': 'A55 v2.10 (09/19/2024)',
      'targets': ['00000000-0000-0000-0000-000000000243',
                  '00000000-0000-0000-0000-000001413535',
                  '00000000-0000-0000-0001-000000010243',
                  '00000000-0000-0000-0001-000000020243']}]

# Download
[Download fwget](https://downloads.linux.hpe.com/SDR/project/fwpp-gen12/fwget-releases.html)

# License
    fwget is open source software licensed under the GPLv2. We're interested in your feedback and pull requests.
    Check the HPE fwget github repository to contribute or clone the latest development branch.

# Changelog
[Release Notes](https://downloads.linux.hpe.com/SDR/project/fwpp-gen12/fwget-releases.html#release-v1.0.5)
