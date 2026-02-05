# Adminis Locuințe - Home Assistant Integration

**Integrare custom Home Assistant pentru platforma [adminislocuinte.ro](https://adminislocuinte.ro)**

Monitorizează facturile de utilități, istoricul plăților și sumele restante direct din Home Assistant.

> **Disclaimer:** Această integrare a fost dezvoltată prin reverse engineering și nu este afiliată sau endorsată de Adminis Locuinte. Dezvoltată de Emanuel Besliu.

## ✨ Caracteristici

- 🔐 **Autentificare securizată** - Credențiale criptate în Home Assistant
- 🏘️ **Multi-locație** - Suport automat pentru apartamente, parcări, boxe
- 💰 **Monitorizare plăți** - Sold restant și istoric detaliat
- 📊 **Breakdown complet** - 34+ categorii de cheltuieli (apă, gaz, încălzire, servicii)
- 🔄 **Actualizare automată** - Refresh la fiecare oră
- 🌍 **Bilingv** - Română și Engleză

## 📦 Instalare

### Metoda 1: HACS (Recomandat - În curând)

1. Deschide HACS în Home Assistant
2. Mergi la "Integrations"
3. Click pe "⋮" → "Custom repositories"
4. Adaugă URL: `https://github.com/emanuelbesliu/homeassistant-adminislocuinte`
5. Categorie: "Integration"
6. Click "Add"
7. Caută "Adminis Locuințe" și instalează

### Metoda 2: Manual

1. Descarcă ultima versiune de pe [GitHub Releases](https://github.com/emanuelbesliu/homeassistant-adminislocuinte/releases)

2. Copiază folderul `adminislocuinte` în directorul `custom_components`:
   ```
   /config/custom_components/adminislocuinte/
   ```

3. Restartează Home Assistant

## ⚙️ Configurare

1. Mergi la **Settings** → **Devices & Services** → **Add Integration**
2. Caută "**Adminis Locuințe**"
3. Introdu **email** și **parola** contului tău adminislocuinte.ro
4. Click **Submit**

După 5 minute, senzorii vor apărea cu datele tale!

## 📊 Senzori Creați

### Senzori Globali (4)

| Senzor | Descriere |
|--------|-----------|
| `sensor.adminis_locuinte_location_count` | Număr total de locații |
| `sensor.adminis_locuinte_total_pending` | Total sume restante (RON) |
| `sensor.adminis_locuinte_last_payment_amount` | Ultima plată efectuată (RON) |
| `sensor.adminis_locuinte_last_payment_date` | Data ultimei plăți |

### Senzori Per-Locație (3 × număr locații)

Pentru fiecare apartament/parcare:

| Senzor | Descriere |
|--------|-----------|
| `sensor.adminis_locuinte_{apt}_monthly_bill` | Factura lunară cu breakdown complet |
| `sensor.adminis_locuinte_{apt}_pending` | Suma restantă pentru această locație |
| `sensor.adminis_locuinte_{apt}_last_payment` | Ultima plată pentru această locație |

**Exemplu pentru Apartament 12:**
- `sensor.adminis_locuinte_12_monthly_bill`
- `sensor.adminis_locuinte_12_pending`
- `sensor.adminis_locuinte_12_last_payment`

## 📈 Date Disponibile

### Breakdown Cheltuieli (34+ categorii)

Fiecare factură include detalii complete:

**Apă & Canalizare:**
- Apă caldă
- Apă rece
- Diferențe apă caldă/rece
- Canalizare

**Energie & Încălzire:**
- Încălzire
- Agent termic
- Energie electrică (iluminat, centrale, ascensor, pompe)
- Gigacalorimetre

**Servicii:**
- Curățenie
- Pază
- Ascensor
- Salubrizare
- Dezinsecție / Deratizare

**Administrare:**
- Administrare generală
- Consultanță
- Cenzor
- Președinte
- Fond reparații

**Și multe altele...**

### Atribute Senzori

Fiecare senzor include atribute detaliate:

```yaml
# Exemplu: sensor.adminis_locuinte_12_monthly_bill
state: 862.12
attributes:
  location_name: "Str. Exemplu nr. 1, bloc A1, ap. 12, Iași"
  location_type: "apartment"
  apartment: "12"
  date: "30.01.2026"
  receipt: "260305BTSD"
  breakdown:
    "Apa calda": 60.74
    "Apa rece": 141.73
    "Incalzire": 136.41
    "Curatenie": 24.90
    # ... (30+ categorii)
```

## 🎨 Dashboard

Vezi [DASHBOARD_EXAMPLE.md](DASHBOARD_EXAMPLE.md) pentru **8 exemple complete** de configurări dashboard:

- Overview Card simplu
- Carduri detaliate per-locație
- Gauge-uri vizuale
- Tabele cu breakdown
- Dashboard complet cu navigare
- Layout mobil
- Grafice și chart-uri

## 🔄 Actualizare Date

- **Interval implicit:** 1 oră
- **Prima actualizare:** Imediat după setup
- **Refresh manual:** Developer Tools → Services → `homeassistant.update_entity`

## 🛠️ Troubleshooting

### Senzorii nu apar

1. Așteaptă 5 minute după configurare
2. Verifică log-urile: Settings → System → Logs
3. Reload integrarea: Settings → Devices & Services → Adminis Locuințe → Reload

### Eroare de autentificare

1. Verifică că email și parola sunt corecte
2. Testează login pe adminislocuinte.ro
3. Șterge integrarea și reconfigurează

### Date lipsă

- Pending payments: Normal să fie 0 dacă nu ai facturi restante
- Counters: API-ul nu returnează date valide momentan (nu afectează funcționalitatea)

### Debug

Adaugă în `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.adminislocuinte: debug
```

## 🤝 Contribuții

Contribuțiile sunt binevenite!

1. Fork repository-ul
2. Creează un branch pentru feature: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Deschide un Pull Request

## 📝 Licență

MIT License - Copyright (c) 2026 Emanuel Besliu

Vezi [LICENSE](LICENSE) pentru detalii complete.

## ⚠️ Disclaimer Legal

Această integrare a fost dezvoltată independent prin reverse engineering al platformei adminislocuinte.ro pentru uz personal și educațional. Nu este afiliată, endorsată sau suportată oficial de Adminis Locuinte sau platformele afiliate.

Utilizarea se face pe propriul risc. Dezvoltatorul nu este responsabil pentru:
- Modificări ale API-ului care pot întrerupe funcționalitatea
- Probleme cauzate de utilizarea incorectă a integrării
- Pierderea datelor sau probleme cu contul adminislocuinte.ro

## 📞 Suport

- 🐛 **Bug reports:** [GitHub Issues](https://github.com/emanuelbesliu/homeassistant-adminislocuinte/issues)
- 💬 **Discuții:** [GitHub Discussions](https://github.com/emanuelbesliu/homeassistant-adminislocuinte/discussions)
- 📖 **Documentație:** [Wiki](https://github.com/emanuelbesliu/homeassistant-adminislocuinte/wiki)

## 🙏 Mulțumiri

Mulțumesc comunității Home Assistant pentru documentație și suport!

---

**Dezvoltat cu ❤️ de Emanuel Besliu**
