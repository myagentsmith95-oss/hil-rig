For machine vision applications (such as USB3 Vision cameras running at high frame rates), standard host controller sharing will result in dropped frames and packet collisions. Because each camera needs a dedicated xHCI controller and its own DMA channel, you must avoid internal USB hubs entirely.
Since you are looking for a mobile or compact deployment (given the initial notebook inquiry), here are the best hardware solutions to achieve 4 to 5+ independent lspci endpoints specifically designed for machine vision.

1. The Industry Standard: Multi-Controller PCIe Cards (for Desktops/Workstations)

If you can pivot to a compact desktop, a short-depth server, or an expansion chassis, you can use a quad-chip PCIe card. These cards place 4 separate controller chips on a single board, using a PCIe switch to give each chip its own dedicated lane.
• StarTech Quad-Channel Card (PEXUSB314A2V2): Features 4 independent Asmedia controllers. In lspci, this single physical card will register as 4 distinct USB controller endpoints.
• Sonnet Allegro Pro (USB3-PRO-4P10): Uses 4 independent controllers to provide full 10Gbps bandwidth to every single port simultaneously.

2. Embedded & Mobile: Machine Vision Industrial Box PCs

If the system must be deployed on a mobile robot, factory floor, or vehicle, several manufacturers build compact, rugged computers explicitly designed for this exact use case. They route multiple physical PCIe lines to separate onboard host controller chips.
• Neousys Technology Nuvo Series: Look at models like the Nuvo-9000 or Nuvo-7000 series. They offer variants explicitly marketed with "4x or 8x Independent USB 3.1 Gen1 Controllers" for machine vision. Each port functions as an isolated lspci device.
• Vecow ECS Series: High-performance, fanless embedded systems that integrate multiple independent USB 3.0/3.1 controllers directly onto the motherboard to ensure zero frame loss across multiple USB3 Vision cameras.

3. The Laptop Workaround: PCIe Expansion over Thunderbolt

If a laptop or notebook is an absolute requirement for your field testing, you can expose true, independent hardware controllers by breaking out the laptop's internal PCIe lanes via a Thunderbolt 3 or USB4 enclosure.
• The Setup: Connect a Thunderbolt 3/4 PCIe Expansion Chassis (such as a Sonnet Echo Express or OWC Mercury Helios) to the laptop.
• The Controller: Install one of the Quad-Controller PCIe cards mentioned in Step 1 into the chassis.
• The Result: Because Thunderbolt natively tunnels PCIe, the laptop's kernel will see the external card exactly as if it were plugged into a desktop motherboard. Running lspci will successfully reveal 4 new, independent hardware USB controller addresses dedicated entirely to your cameras.
Would you prefer to look into compact industrial computers (Box PCs) that can handle factory/mobile environments, or should we explore the Thunderbolt enclosure + PCIe card route to keep using a laptop?

========++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++=======

Based on your lspci output, you are currently running an older system with 3 independent hardware USB controllers (two Intel EHCI controllers built into the 6 Series chipset and one discrete NEC USB 3.0 chip).
If you are looking to step up to a system that exposes 5 or more independent hardware USB controller endpoints natively in lspci, you will need to look at High-End Desktop (HEDT) platforms, Server/Workstation motherboards, or specialized Industrial PCs, rather than standard consumer laptops.

Why Modern Systems Differ from Your Output

Your current output shows an older architecture where USB 2.0 (EHCI) and USB 3.0 (xHCI) were split into separate controller endpoints (00:1a.0, 00:1d.0, and 0a:00.0). Modern systems rely almost entirely on xHCI (eXtensible Host Controller Interface). Under xHCI, a single hardware controller endpoint in lspci handles both USB 2.0, 3.0, and newer speeds simultaneously across many multiplexed ports.

How to Achieve 5+ Independent Controllers


1. High-End Desktop (HEDT) & Workstation Motherboards

Platforms like AMD Threadripper (WRX80/TRX50) or Intel Xeon Workstations inherently feature massive PCIe lane counts and complex chipsets.
• They often expose 3 to 4 independent USB controllers natively across the CPU roots and the chipset roots.
• You can easily reach 5+ independent controllers by plugging in discrete PCIe-to-USB expansion cards that feature dedicated per-port controller chips (such as Quad-chip StarTech or Sonnet USB PCIe cards).

2. Specialized Industrial / Embedded PCs

Industrial automation and machine vision systems frequently require dedicated, unshared bandwidth for multiple high-speed USB cameras.
• Look for rugged/industrial box PCs (from brands like Neousys, Advantech, or Vecow).
• These systems are explicitly advertised as having "4x or 8x Independent USB 3.0/3.1 Controllers" built directly onto the carrier board to prevent cross-talk and bandwidth choking.

3. Single Board Computers (SBCs) with PCIe

Some advanced ARM or x86 Single Board Computers offer exposed PCIe slots or multiple discrete on-board controller chips mapped to separate PCIe addresses for specific robotics or vision processing workflows.
Are you trying to isolate bandwidth for machine vision cameras (like USB3 Vision), SDRs, or high-speed data acquisition?
If you can share your target environment (e.g., a server rack, a desktop, or a mobile deployment), I can pinpoint the exact hardware expansion cards or industrial boards that will give you 5 distinct lspci entries.

