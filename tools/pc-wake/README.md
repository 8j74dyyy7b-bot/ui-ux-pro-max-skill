# PC Wake – PC aus der Ferne einschalten

Kleines Wake-on-LAN-Tool (Python 3, keine Zusatzpakete). Es läuft auf einem
Gerät, das **immer an** ist und im **selben Heimnetz** wie der PC hängt
(Raspberry Pi, NAS, alter Laptop) und schickt dem PC das „Aufwach-Signal“.

## 1. PC vorbereiten (einmalig)

1. **BIOS/UEFI:** „Wake on LAN“ / „Power On by PCI-E“ aktivieren. „ErP“ bzw.
   „Deep Sleep“ ausschalten.
2. **Windows:** Geräte-Manager → Netzwerkadapter → Eigenschaften →
   - *Energieverwaltung:* „Gerät kann den Computer aus dem Ruhezustand aktivieren“
     und „Nur Magic Packet…“ anhaken.
   - *Erweitert:* „Wake on Magic Packet“ = Aktiviert.
3. **Windows-Schnellstart ausschalten** (Systemsteuerung → Energieoptionen →
   „Auswählen, was beim Drücken des Netzschalters geschehen soll“).
4. PC per **LAN-Kabel** verbinden (WLAN-WoL klappt meist nicht).
5. MAC-Adresse notieren: `ipconfig /all` → „Physische Adresse“.

## 2. Testen im Heimnetz

```bash
python3 pc_wake.py wake AA:BB:CC:DD:EE:FF
```

## 3. Weboberfläche fürs Handy

```bash
python3 pc_wake.py serve --mac AA:BB:CC:DD:EE:FF --pin 4711 \
    --host 192.168.178.50 --name "Gaming-PC"
```

Dann am Handy `http://<IP-des-Pi>:8080` öffnen, PIN eingeben, Knopf drücken.
`--host` (IP des PCs) ist optional und zeigt online/offline an.

Autostart auf dem Raspberry Pi (`crontab -e`):

```
@reboot python3 /home/pi/pc_wake.py serve --mac AA:BB:CC:DD:EE:FF --pin 4711
```

## 4. Von unterwegs (außerhalb des WLANs)

Die Seite **nicht direkt per Portfreigabe ins Internet stellen** (nur HTTP, nur
PIN-Schutz). Besser:

- **VPN der FRITZ!Box** (WireGuard) oder **Tailscale** auf Pi und Handy –
  dann ist die Seite von überall erreichbar, aber nur für dich.

**Tipp FRITZ!Box:** Die kann WoL schon selbst – Heimnetz → Netzwerk → PC
bearbeiten → „Computer starten“, oder in der App *MyFRITZ!App*. Dann brauchst
du gar kein Zusatzgerät.
