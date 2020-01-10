#!/usr/bin/env python
# encoding:utf8
"""NetworkManager command line dmenu script.

To add new connections or enable/disable networking requires policykit
permissions setup per:
https://wiki.archlinux.org/index.php/NetworkManager#Set_up_PolicyKit_permissions

OR running the script as root

Add dmenu formatting options and default terminal if desired to
~/.config/networkmanager-dmenu/config.ini

"""

### TODO
# - Add system notifications hook (for use with e.g. dunst)
# - Second pass over which NetworkManager methods actually need to be methods and not external functions
# - Make NetworkManager methods private as needed
# - Abstract away "no security" string and put it in config
###

import locale
import sys
import os
import argparse
import uuid
from subprocess import Popen, PIPE, DEVNULL

import gi

gi.require_version("NM", "1.0")
from gi.repository import GLib, NM

ENV = os.environ.copy()
ENV["LC_ALL"] = "C"
ENC = locale.getpreferredencoding()


def add_dmenu_prompt(dmenu_command, prompt="Networks"):
    return dmenu_command.extend(["-p", prompt])


def is_modemmanager_installed():
    """Check if ModemManager is installed"""

    try:
        Popen(["ModemManager"], stdout=DEVNULL, stderr=DEVNULL).communicate()
    except OSError:
        return False

    return True


def ssid_to_utf8(ap):
    """ Convert binary ssid to utf-8 """
    ssid = ap.get_ssid()

    if not ssid:
        return ""

    ret = NM.utils_ssid_to_utf8(ssid.get_data())

    return ret


def get_ap_security(ap):
    """Parse an access point's security flags and return the type of security present.

    Args:
        ap (NM.AccessPoint): Wireless access point.

    Returns:
        sec_str (str): String like 'WPA2' etc.
    """
    flags = ap.get_flags()
    wpa_flags = ap.get_wpa_flags()
    rsn_flags = ap.get_rsn_flags()
    security_str = []

    if (
        (flags & getattr(NM, "80211ApFlags").PRIVACY)
        and (wpa_flags == 0)
        and (rsn_flags == 0)
    ):
        security_str += ["WEP"]

    if wpa_flags != 0:
        security_str += ["WPA1"]

    if rsn_flags != 0:
        security_str += ["WPA2"]

    if (wpa_flags & getattr(NM, "80211ApSecurityFlags").KEY_MGMT_802_1X) or (
        rsn_flags & getattr(NM, "80211ApSecurityFlags").KEY_MGMT_802_1X
    ):
        security_str += ["802.1X"]

    # If there is no security use "--"
    if not security_str:
        security_str += ["--"]

    return " ".join(security_str)


def strength_to_bars(wifi_strength):
    """Turn numeric Wifi signal strength into pretty-print representation."""
    if wifi_strength > 90:
        return "▮▮▮▮"
    elif wifi_strength > 70:
        return "▮▮▮▯"
    elif wifi_strength > 50:
        return "▮▮▯▯"
    elif wifi_strength > 30:
        return "▮▯▯▯"
    else:
        return "▯▯▯▯"


class Action:
    """Helper class that associates a Wifi access point, a function to be performed
    on it, and its arguments.
    """

    def __init__(self, name, func, args=None, is_active=False):
        """
        Args:
            name (str): Name of the access point, includes its security type and signal strength.
            func (function): Function that takes [name] as a first argument.
            args (list): List of args to pass to [func].
            is_active (bool): True if the AP in question is the currently active one.
        """
        self.name = name
        self.func = func
        self.is_active = is_active

        if not args:
            self.args = None
        elif isinstance(args, list):
            self.args = args
        else:
            self.args = [args]

    def __str__(self):
        return self.name

    def __call__(self):
        if self.args:
            self.func(*self.args)
        else:
            self.func()


class NetworkMenu:
    """Wrapper class around a rofi/dmenu-based network selection menu.

    Uses externally-supplied config options to auto-generate rofi/dmenu calls
    that allow interaction with a system's Network Manager.
    """

    def __init__(self, main_loop, client, conf):
        """Gather all the information required to generate a network selection menu.

        Combine a NetworkManager client and the GTK+ toolkit to scan for surrounding
        network access points, sort them by strength, and create a list of "actions"
        allowing you to activate/deactivate each one. This enables you to then run
        the .selection() method to prompt the user for action.

        Args:
            main_loop (GLib.MainLoop): Python hook into the GTK+ toolkit.
            client (NM.Client): NetworkManager client, allows interaction with the NM.
            conf (argparse namespace): Namespace for CLI args.
        """
        # Network and system interfaces
        self.conf = conf
        self.main_loop = main_loop
        self.client = client
        self.conns = self.client.get_connections()

        # Rofi/dmenu config
        if conf.rofi:
            self.menu = "rofi"
            self.rofi_theme = conf.rofi_theme
            self.rofi_highlight_active = conf.rofi_highlight_active
            self.rofi_obscure_pw = conf.rofi_obscure_pw
        elif conf.dmenu:
            self.menu = "dmenu"
            self.dmenu_style = conf.dmenu_style

        self.custom_prompt = conf.prompt

        # External programs config
        self.terminal = conf.terminal
        self.use_gui_nm_editor = conf.use_gui_nm_editor

        # Scan for active connections and pick a network adapter to work on
        self.active_connections = self.client.get_active_connections()
        self.adapter = self.choose_adapter()

        # Generate list of possible actions for each network type
        if self.adapter:
            self.ap_actions = self.create_ap_actions(
                *self.create_ap_list(self.active_connections)
            )
        else:
            self.ap_actions = []

        vpns = [c for c in self.conns if c.is_type(NM.SETTING_VPN_SETTING_NAME)]
        eths = [c for c in self.conns if c.is_type(NM.SETTING_WIRED_SETTING_NAME)]
        blues = [c for c in self.conns if c.is_type(NM.SETTING_BLUETOOTH_SETTING_NAME)]

        self.vpn_actions = self.create_vpn_actions(vpns)
        self.eth_actions = self.create_eth_actions(eths)
        self.blue_actions = self.create_blue_actions(blues)

        if is_modemmanager_installed():
            gsms = [c for c in self.conns if c.is_type(NM.SETTING_GSM_SETTING_NAME)]
            self.gsm_actions = self.create_gsm_actions(gsms)
            self.wwan_actions = self.create_wwan_actions()
        else:
            self.gsm_actions = []
            self.wwan_actions = []

        # Other actions involve enabling/disabling adapters, rescanning available connections, etc.
        self.other_actions = self.create_other_actions()

    def _dmenu_call(self, num_lines=1, prompt="Networks"):
        """
        Return a list of strings that constitute a dmenu call when joined together.

        NOTE: Additional styling options are set by passing --dmenu style to the module,
        and are stored in self.dmenu_style.

        Args:
            num_lines (int): Number of lines, passed as an '-l' parameter to rofi.
            prompt (str): Prompt to display in rofi's inputbar.

        Returns:
            result (list): Must be a list of single-word strings, where the first is a
                           command and the rest are its arguments.
        """
        result = ["dmenu", "-i"]
        cmd_args = []

        # Unpack any supplied CLI args for dmenu
        if self.dmenu_style:
            kwargs = {
                k: v for k, v in zip(self.dmenu_style[::2], self.dmenu_style[1::2])
            }

        # Override num_lines if supplied
        lines_override = kwargs.pop("l", None)
        if lines_override:
            num_lines = min(num_lines, int(lines_override))

        cmd_args.extend(["-l", str(num_lines)])

        # Override prompt if supplied
        if prompt == "Networks":
            prompt_override = kwargs.pop("-p", None) or self.custom_prompt
            if prompt_override:
                prompt = prompt_override

        cmd_args.extend(["-p", str(prompt)])

        # Loop through remaining kwargs
        kwargs = [("-{}".format(k), v) for k, v in kwargs.items()]
        cmd_args.extend([str(i) for kv in kwargs for i in kv])

        # Filter out empty items
        cmd_args = list(filter(None, cmd_args))

        result.extend(cmd_args)

        return result

    def _rofi_call(self, num_lines=1, prompt="Networks", active_lines=None):
        """
        Return a list of strings that constitute a rofi call when joined together.

        NOTE: Rofi does not override the #listview { lines: } setting with CLI args
        like "-l" or "-lines". If your theme features the setting, num_lines is
        completely redundant.

        Args:
            num_lines (int): Number of lines, passed as an '-l' parameter to rofi.
            prompt (str): Prompt to display in rofi's inputbar.
            active_lines (str): Comma-separated ints, indicating lines marked as active.

        Returns:
            result (list): Must be a list of single-word strings, where the first is a
                           command and the rest are its arguments.
        """
        result = ["rofi", "-dmenu", "-i"]

        # Rofi doesn't like 0-length lines
        num_lines = max(num_lines, 1)
        cmd_args = ["-l", str(num_lines)]

        # Turn list of active lines into a CLI argument
        if self.rofi_highlight_active and active_lines:
            cmd_args.extend(["-a", ",".join([str(n) for n in active_lines])])

        # Use custom prompt for Networks menu if supplied
        if prompt == "Networks" and self.custom_prompt:
            prompt = self.custom_prompt

        cmd_args.extend(["-p", str(prompt)])

        # Use custom theme if supplied
        if self.rofi_theme:
            cmd_args.extend(["-theme", self.rofi_theme])

        if prompt == "Password" and self.rofi_obscure_pw:
            cmd_args.extend(["-password"])

        # Filter out empty items
        cmd_args = list(filter(None, cmd_args))

        result.extend(cmd_args)

        return result

    def dmenu_cmd(self, num_lines=1, prompt="Networks", active_lines=None):
        if self.menu == "rofi":
            return self._rofi_call(num_lines, prompt, active_lines)
        elif self.menu == "dmenu":
            return self._dmenu_call(num_lines, prompt)

    ### WIFI CONNECTIVITY ###

    def choose_adapter(self):
        """If there is more than one wifi adapter installed, ask which one to use."""
        devices = self.client.get_devices()
        devices = [i for i in devices if i.get_device_type() == NM.DeviceType.WIFI]

        if not devices:
            return None
        elif len(devices) == 1:
            return devices[0]
        else:
            device_names = "\n".join([d.get_iface() for d in devices]).encode(ENC)

            sel = (
                Popen(
                    self.dmenu_cmd(len(devices), prompt="Adapter"),
                    stdin=PIPE,
                    stdout=PIPE,
                    env=ENV,
                )
                .communicate(input=device_names)[0]
                .decode(ENC)
            )

            if not sel.strip():
                sys.exit()

            devices = [i for i in devices if i.get_iface() == sel.strip()]
            assert len(devices) == 1

            return devices[0]

    def create_ap_list(self, active_connections):
        """Generate list of access points. Remove duplicate APs, keeping strongest
        ones and the active one if any.

        The output of this is designed to feed straight into create_ap_actions().

        Args:
            active_connections (list): List of all active connections.
        Returns:
            aps (list): List of all available access points.
            active_ap (NM.AccessPoint): Active access point.
            active_ap_con (NM.ActiveConnection): Active Connection.
        """
        aps = []
        ap_names = []

        # Get currently active AP, detect all APs available
        active_ap = self.adapter.get_active_access_point()
        aps_all = sorted(
            self.adapter.get_access_points(),
            key=lambda a: a.get_strength(),
            reverse=True,
        )
        conns_cur = [
            c
            for c in self.conns
            if c.get_setting_wireless() is not None
            and c.get_setting_wireless().get_mac_address()
            == self.adapter.get_permanent_hw_address()
        ]

        # Get a connection to the currently active access point
        try:
            ap_conns = active_ap.filter_connections(conns_cur)
            active_ap_name = ssid_to_utf8(active_ap)
            active_ap_con = [
                ac for ac in active_connections if ac.get_connection() in ap_conns
            ]
        except AttributeError:
            active_ap_name = None
            active_ap_con = []

        if len(active_ap_con) > 1:
            raise ValueError(
                "Multiple connection profiles match the wireless access point"
            )
        active_ap_con = active_ap_con[0] if active_ap_con else None

        for ap in aps_all:
            ap_name = ssid_to_utf8(ap)

            # Skip adding AP if it's not active but same name as active AP
            if ap != active_ap and ap_name == active_ap_name:
                continue

            if ap_name not in ap_names:
                ap_names.append(ap_name)
                aps.append(ap)

        return aps, active_ap, active_ap_con

    def get_password(self):
        """
        Prompt user for password and return it.

        Returns:
            sel (str): Password.
        """
        sel = (
            Popen(
                self.dmenu_cmd(num_lines=0, prompt="Passphrase"),
                stdin=PIPE,
                stdout=PIPE,
            )
            .communicate()[0]
            .decode(ENC)
        )

        if not sel:
            sys.exit()
        else:
            return sel

    def create_wifi_profile(self, ap, password):
        """Create a NetworkManager profile given an AP and passphrase.

        See https://cgit.freedesktop.org/NetworkManager/NetworkManager/tree/examples/python/gi/add_connection.py
        and https://cgit.freedesktop.org/NetworkManager/NetworkManager/tree/examples/python/dbus/add-wifi-psk-connection.py

        Args:
            ap (NM.AccessPoint): Access point you want to connect to.
            password (str): Optional password for the access point.

        Returns:
            profile (NM.SimpleConnection): NetworkManager profile object.
        """
        ap_sec = get_ap_security(ap)
        profile = NM.SimpleConnection.new()

        s_con = NM.SettingConnection.new()
        s_con.set_property(NM.SETTING_CONNECTION_ID, ssid_to_utf8(ap))
        s_con.set_property(NM.SETTING_CONNECTION_UUID, str(uuid.uuid4()))
        s_con.set_property(NM.SETTING_CONNECTION_TYPE, "802-11-wireless")
        profile.add_setting(s_con)

        s_wifi = NM.SettingWireless.new()
        s_wifi.set_property(NM.SETTING_WIRELESS_SSID, ap.get_ssid())
        s_wifi.set_property(NM.SETTING_WIRELESS_MODE, "infrastructure")
        s_wifi.set_property(
            NM.SETTING_WIRELESS_MAC_ADDRESS, self.adapter.get_permanent_hw_address()
        )
        profile.add_setting(s_wifi)

        s_ip4 = NM.SettingIP4Config.new()
        s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        profile.add_setting(s_ip4)

        s_ip6 = NM.SettingIP6Config.new()
        s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        profile.add_setting(s_ip6)

        if ap_sec != "--":
            s_wifi_sec = NM.SettingWirelessSecurity.new()

            if "WPA" in ap_sec:
                s_wifi_sec.set_property(
                    NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk"
                )
                s_wifi_sec.set_property(NM.SETTING_WIRELESS_SECURITY_AUTH_ALG, "open")
                s_wifi_sec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            elif "WEP" in ap_sec:
                s_wifi_sec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "None")
                s_wifi_sec.set_property(
                    NM.SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE, NM.WepKeyType.PASSPHRASE
                )
                s_wifi_sec.set_wep_key(0, password)
            profile.add_setting(s_wifi_sec)

        return profile

    def verify_conn(self, result, data):
        """Callback function for add_and_activate_connection_async.

        Check if connection completes successfully. Delete the connection if there
        is an error.
        """
        try:
            act_conn = self.client.add_and_activate_connection_finish(result)
            conn = act_conn.get_connection()
            conn.verify()
            conn.verify_secrets()
            data.verify()
            data.verify_secrets()
        except GLib.Error:
            try:
                conn.delete()
            except UnboundLocalError:
                pass
        finally:
            self.main_loop.quit()

    def set_new_connection(self, ap, password):
        """Set up a new NetworkManager connection.

        See https://developer.gnome.org/libnm/stable/NMClient.html#nm-client-add-and-activate-connection-async

        Args:
            ap (NM.AccessPoint): Access point you want to connect to.
            password (str): Optional password for the access point.
        """
        password = str(password).strip()
        profile = self.create_wifi_profile(ap, password)
        self.client.add_and_activate_connection_async(
            profile,
            self.adapter,
            ap.get_path(),
            None,
            self.verify_conn,
            profile
        )
        self.main_loop.run()

    def process_ap(self, ap, is_active):
        """Activate/Deactivate a connection, optionally prompting user for password.

        Args:
            ap (NM.AccessPoint or NM.ActiveConnection): Wifi access point.
            is_active (bool): True if there is currently an active connection with the AP.
            adapter (NM.DeviceWifi): Active network adapter.
        """
        if is_active:
            # If it's an active connection, deactivate it
            self.client.deactivate_connection_async(ap)
        else:
            # If its an AP, get the connection relating to that AP and activate it
            conns_cur = [
                c
                for c in self.conns
                if c.get_setting_wireless()
                and c.get_setting_wireless().get_mac_address()
                == self.adapter.get_permanent_hw_address()
            ]
            con = ap.filter_connections(conns_cur)

            if len(con) > 1:
                raise ValueError("There are multiple connections possible")

            if len(con) == 1:
                self.client.activate_connection_async(con[0])
            else:
                if get_ap_security(ap) != "--":
                    password = self.get_password()
                else:
                    password = ""

                self.set_new_connection(ap, password)

    def create_ap_actions(self, aps, active_ap, active_connection):
        """For a list of APs, return a corresponding list of Actions.

        The Actions in question are [activate/deactivate] and are derived from
        the APs' current connection status.

        Args:
            aps (list): List of all available access points.
            active_ap (NM.AccessPoint): Currently active access point.
            active_connection (NM.ActiveConnection): Connection to the currently active AP.

        Returns:
            ap_actions (list): List of Action objects, one for each AP.
        """
        active_ap_bssid = active_ap.get_bssid() if active_ap else ""

        # List all AP names and their security types (WPA, ...)
        # Max lengths of each type are used below to ensure consistent spacing
        names = [ssid_to_utf8(ap) for ap in aps]
        max_len_name = max([len(name) for name in names]) if names else 0
        secs = [get_ap_security(ap) for ap in aps]
        max_len_sec = max([len(sec) for sec in secs]) if secs else 0

        ap_actions = []

        for ap, name, sec in zip(aps, names, secs):
            is_active = ap.get_bssid() == active_ap_bssid

            # Change numeric Wifi strength to pretty-print representation
            bars = strength_to_bars(ap.get_strength())

            # Generate a string containing AP name, security type, signal strength
            action_name = "{:<{}s}   {:<{}s}   {:<}".format(
                name, max_len_name, sec, max_len_sec, bars
            )

            if is_active:
                ap_actions.append(
                    Action(
                        name=action_name,
                        func=self.process_ap,
                        args=[active_connection, True],
                        is_active=True,
                    )
                )
            else:
                ap_actions.append(
                    Action(
                        name=action_name,
                        func=self.process_ap,
                        args=[ap, False],
                        is_active=False,
                    )
                )

        return ap_actions

    ### OTHER CONNECTIVITY ###

    def process_connection(self, con, activate):
        """Activate/deactive connections other than Wifi.

        Equivalent to process_ap().

        Args:
            con: Either an NM.ActiveConnection or an inactive NM.Connection.
            activate (bool): What to do with the connection.
        """
        if activate:
            self.client.activate_connection_async(con)
        else:
            self.client.deactivate_connection_async(con)

    def create_connection_actions(self, cons, active_cons, label):
        """Helper function to create Action lists for connections other than Wifi.

        Args:
            cons (list): List of available NM.Connection objects of a specific protocol.
            active_cons (list): List of NM.ActiveConnection objects, indicating currently active conns.
            label (str): Name of the specific protocol to generate actions for.

        Returns:
            actions (list): List of Action objects.
        """
        active_con_ids = [a.get_id() for a in active_cons]
        actions = []

        for con in cons:
            is_active = con.get_id() in active_con_ids
            action_name = u"{}:{}".format(con.get_id(), label)

            if is_active:
                active_connection = [
                    a for a in active_cons if a.get_id() == con.get_id()
                ]

                if len(active_connection) != 1:
                    raise ValueError(
                        u"Multiple active connections match"
                        " the connection: {}".format(con.get_id())
                    )
                active_connection = active_connection[0]

                actions.append(
                    Action(
                        name=action_name,
                        func=self.process_connection,
                        args=[active_connection, False],
                        active=True,
                    )
                )
            else:
                actions.append(
                    Action(
                        name=action_name,
                        func=self.process_connection,
                        args=[con, True],
                        is_active=False,
                    )
                )

        return actions

    def create_vpn_actions(self, vpns):
        """Same as create_ap_actions() for VPN connections."""
        active_vpns = [a for a in self.active_connections if a.get_vpn()]
        return self.create_connection_actions(vpns, active_vpns, "VPN")

    def create_eth_actions(self, eths):
        """Same as create_ap_actions() for Ethernet connections."""
        active_eths = [
            a for a in self.active_connections if "ethernet" in a.get_connection_type()
        ]
        return self.create_connection_actions(eths, active_eths, "Eth")

    def create_blue_actions(self, blues):
        """Same as create_ap_actions() for Bluethooth connections."""
        active_blues = [
            a
            for a in self.active_connections
            if a.get_connection()
            and a.get_connection().is_type(NM.SETTING_BLUETOOTH_SETTING_NAME)
        ]
        return self.create_connection_actions(blues, active_blues, "Bluetooth")

    def create_gsm_actions(self, gsms):
        """Same as create_ap_actions() for GSM connections."""
        active_gsms = [
            a
            for a in self.active_connections
            if a.get_connection()
            and a.get_connection().is_type(NM.SETTING_GSM_SETTING_NAME)
        ]
        return self.create_connection_actions(gsms, active_gsms, "GSM")

    ### SYSTEM INTERACTION ###

    def toggle_wwan(self, enable):
        """Enable/disable WWAN."""
        self.client.wwan_set_enabled(enable)

    def create_wwan_actions(self):
        """Same as create_ap_actions() for WWAN connections."""
        wwan_enabled = self.client.wwan_get_enabled()
        wwan_action = "Disable" if wwan_enabled else "Enable"

        return [
            Action(
                name="{} WWAN".format(wwan_action),
                func=self.toggle_wwan,
                args=not wwan_enabled,
            )
        ]

    def toggle_networking(self, enable):
        """Enable/disable networking."""
        self.client.networking_set_enabled(enable)

    def toggle_wifi(self, enable):
        """Enable/disable Wifi."""
        self.client.wireless_set_enabled(enable)

    def launch_connection_editor(self, term="xterm", gui_if_available=True):
        """Launch nmtui or the GUI nm-connection-editor.

        Args:
            term (str): Name of the terminal emulator you want to use.
            gui_if_available (bool): Always prefer nm-connection-editor if installed.
        """
        if gui_if_available:
            try:
                Popen(["nm-connection-editor"]).communicate()
            except OSError:
                Popen([term, "-e", "nmtui"]).communicate()
        else:
            # TODO: there must be more emulators that don't need the -e flag
            if term == "kitty":
                Popen([term, "nmtui"]).communicate()
            else:
                Popen([term, "-e", "nmtui"]).communicate()

    def delete_connection(self):
        """Display list of NM connections and delete the selected one."""
        # Generate list of Delete Actions for saved connections
        conn_acts = [Action(c.get_id(), c.delete) for c in self.conns]
        conn_names = "\n".join([str(c) for c in conn_acts]).encode(ENC)

        # Prompt user
        sel = (
            Popen(
                self.dmenu_cmd(len(conn_acts), prompt="Delete"),
                stdin=PIPE,
                stdout=PIPE,
                env=ENV,
            )
            .communicate(input=conn_names)[0]
            .decode(ENC)
        )

        if not sel.strip():
            sys.exit()

        action = [c for c in conn_acts if str(c) == sel.rstrip("\n")]
        assert len(action) == 1, "Selection was ambiguous: {}".format(str(sel))

        action[0]()

    def rescan_wifi(self):
        """Rescan Wifi Access Points."""
        for dev in self.client.get_devices():
            if type(dev) == NM.DeviceWifi:
                try:
                    dev.request_scan()
                except gi.repository.GLib.Error as err:
                    if not err.code == 6:  # Too frequent rescan error
                        raise err

    def create_other_actions(self):
        """Return list of other actions that can be taken.

        Includes toggling wifi on/off, re-scanning connections, etc.
        """
        # Enable/disable flags for hardware
        networking_enabled = self.client.networking_get_enabled()
        networking_action = "Disable" if networking_enabled else "Enable"
        wifi_enabled = self.client.wireless_get_enabled()
        wifi_action = "Disable" if wifi_enabled else "Enable"

        actions = [
            Action(
                name="{} Wifi".format(wifi_action),
                func=self.toggle_wifi,
                args=[not wifi_enabled],
            ),
            Action(
                name="{} Networking".format(networking_action),
                func=self.toggle_networking,
                args=[not networking_enabled],
            ),
            Action(
                name="Launch Connection Manager",
                func=self.launch_connection_editor,
                args=[self.terminal, self.use_gui_nm_editor],
            ),
            Action(name="Delete a Connection", func=self.delete_connection),
        ]

        if wifi_enabled:
            actions.append(Action("Rescan Wifi Networks", self.rescan_wifi))

        return actions

    ### USER INTERACTION ###

    def get_selection(self):
        """Combine all _actions attributes found in the class and send them to rofi/dmenu."""
        empty_action = [Action("", None)]

        all_actions = []
        all_actions += self.eth_actions + empty_action if self.eth_actions else []
        all_actions += self.ap_actions + empty_action if self.ap_actions else []
        all_actions += self.vpn_actions + empty_action if self.vpn_actions else []
        all_actions += (
            self.gsm_actions + empty_action
            if (self.gsm_actions and self.wwan_actions)
            else []
        )
        all_actions += self.blue_actions + empty_action if self.blue_actions else []
        all_actions += self.wwan_actions + empty_action if self.wwan_actions else []
        all_actions += self.other_actions

        if self.menu == "rofi" and self.rofi_highlight_active:
            inp = [str(a) for a in all_actions]
        else:
            inp = [("** " if a.is_active else "   ") + str(a) for a in all_actions]

        active_lines = [
            idx for idx, action in enumerate(all_actions) if action.is_active
        ]

        inp_bytes = "\n".join([i for i in inp]).encode(ENC)
        command = self.dmenu_cmd(len(inp), active_lines=active_lines)

        # Open dmenu
        sel = (
            Popen(command, stdin=PIPE, stdout=PIPE, env=ENV)
            .communicate(input=inp_bytes)[0]
            .decode(ENC)
        )

        if not sel.strip():
            sys.exit()

        # Indices of inputs that match what was selected by user
        action_idx = [idx for idx, i in enumerate(inp) if str(i) == sel.rstrip("\n")]

        assert len(action_idx) == 1, "Selection was ambiguous: '{}'".format(
            str(sel.strip())
        )

        # Actual action matching user input
        action = all_actions[action_idx[0]]

        return action


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Mutually exclusive arguments
    exclusive = parser.add_mutually_exclusive_group(required=True)
    exclusive.add_argument(
        "-dmenu",
        action="store_true",
        help="Use dmenu as interface. Mutually exclusive with '-rofi'.",
    )
    exclusive.add_argument(
        "-rofi",
        action="store_true",
        help="Use rofi as interface. Mutually exclusive with '-dmenu'.",
    )

    # Optional arguments
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Custom prompt for network selection menu.",
    )
    parser.add_argument(
        "--use_gui_nm_editor",
        action="store_true",
        help="Attempt to use GUI nm-connection-editor tool instead of nmtui.",
    )
    parser.add_argument(
        "--terminal",
        type=str,
        default="xterm",
        help="Name of terminal command to use for nmtui.",
    )

    # Rofi-specific
    parser.add_argument(
        "--rofi_theme",
        type=str,
        default=None,
        help="Path to .rasi file used to style rofi window.",
    )
    parser.add_argument(
        "--rofi_highlight_active",
        action="store_true",
        help="Use rofi CSS to highlight active connections instead of prepending with '** ' like dmenu.",
    )
    parser.add_argument(
        "--rofi_obscure_pw",
        action="store_true",
        help="Obscure passwords typed into rofi.",
    )

    # Dmenu-specific
    parser.add_argument(
        "--dmenu_style",
        nargs="*",
        help="Dmenu styling options. Expects sequence of [key] [value] pairs. Does not support -i or -b.",
    )

    conf = parser.parse_args()

    menu = NetworkMenu(main_loop=GLib.MainLoop(), client=NM.Client.new(None), conf=conf)

    menu.selection = menu.get_selection()

    menu.selection()

    sys.exit()
