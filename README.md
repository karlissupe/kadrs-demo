# KADRS! Foto uzdevumu spēle

Pirmā darbojošā versija ar 5–10 komandām un līdz 10 foto uzdevumiem. Visi teksti latviešu valodā.

## Palaišana

Nepieciešams Python 3.10+.

```bash
cd kadrs_web
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
pip install -r requirements.txt
```

Iestati savu administratora paroli un sesiju slepeno atslēgu:

```bash
# Linux/macOS
export ADMIN_PASSWORD='NomainiUzStipruParoli'
export APP_SECRET='Ievieto-garu-nejaušu-unikālu-tekstu'
uvicorn main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
$env:ADMIN_PASSWORD='NomainiUzStipruParoli'
$env:APP_SECRET='Ievieto-garu-nejaušu-unikālu-tekstu'
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Atver `http://localhost:8000` (spēlētāja skats) un `http://localhost:8000/admin` (administrators).

### Spēle uz telefoniem

Pieslēdz telefonu un datoru vienam Wi-Fi tīklam. Telefonā atver `http://DATORA-LOKĀLĀ-IP:8000`. Datora ugunsmūrim jāatļauj ienākoši savienojumi portā 8000. Pārliecinies, ka Wi-Fi viesu tīkla izolācija nav ieslēgta.

## Kā lietot

1. Administratora lapā pieslēdzies ar savu `ADMIN_PASSWORD`.
2. Atver **Komandas**, lai redzētu astoņas sākotnējās komandas un to sešzīmju piekļuves kodus. Kodu vari nokopēt un nosūtīt komandai. Var pievienot vēl līdz 10 komandām vai dzēst komandas bez iesniegumiem.
3. Atver **Uzdevumi**, lai labotu astoņus sākotnējos uzdevumus, pievienotu līdz 10 uzdevumiem kopā un pēc vēlēšanās augšupielādētu parauga attēlu katram uzdevumam.
4. Spēlētājs ievada komandas kodu, izvēlas uzdevumu un iesūta fotogrāfiju.
5. Administrators sadaļā **Iesniegumi** apskata foto, apstiprina vai noraida. Noraidītu foto komanda var iesūtīt atkārtoti.
6. Rezultāti komandām atjaunojas automātiski ik pēc 15 sekundēm, administratoram ik pēc 12 sekundēm.

## Datu glabāšana

SQLite datubāze un attēli glabājas `data/` mapē. Šo mapi **regulāri dublē**. Iesūtītās fotogrāfijas ir pieejamas tikai savai komandai un administratoram. Citu komandu attēli nav publiski; publiski redzama tikai rezultātu tabula. Augšupielādes tiek apstrādātas un pārveidotas uz JPG; EXIF metadati netiek saglabāti.

## Izvietošana internetā

Tikai lokālai testēšanai pietiek ar `uvicorn`. Publiskai spēlei izmanto serveri ar **HTTPS** (piemēram, VPS un Caddy/Nginx reverso starpniekserveri), iestati `SECURE_COOKIES=1` un obligāti `APP_SECRET` un stipru `ADMIN_PASSWORD`. Izmanto **pastāvīgu datu disku**: hostings, kurā faili pazūd pēc pārstartēšanas, nav piemērots bez ārējas datubāzes un attēlu glabātuves.

Šī ir MVP versija, nevis lielas slodzes produkcijas sistēma. Pirms publiskas izmantošanas vēlams pievienot pieprasījumu ierobežošanu, centralizētu žurnālošanu, datu dzēšanas politiku, HTTPS, dublēšanu un servera pieejamības uzraudzību. Dalībniekiem jāsaņem informācija par foto uzglabāšanu un dzēšanas kārtību.
