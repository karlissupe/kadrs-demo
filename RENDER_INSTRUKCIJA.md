# KADRS! Demo izvietošana GitHub + Render (0 €)

Šis ir **demonstrācijas** projekts, paredzēts komandas biedru atsauksmēm. Render Free nodrošina HTTPS, taču lokālā SQLite datubāze un fotogrāfijas ir **nepastāvīgas**: tās var pazust pēc restartēšanas, pārizvietošanas vai servera nomaiņas. Neizmanto īstam pasākumam ar nozīmīgiem datiem bez pastāvīgas glabāšanas.

## 1. Ievieto kodu GitHub

1. Atver github.com un izveido jaunu repozitoriju, piemēram, `kadrs-demo`.
2. Augšupielādē **šī arhīva mapes saturu** repozitorija saknē (lai `main.py` un `render.yaml` būtu saknē). ZIP fails GitHub jāatspiež pirms failu augšupielādes.
3. Nepievieno `data/` direktoriju vai paroles. `.gitignore` jau izslēdz `data/`.
4. GitHub Free lietotājs var veidot publisku repozitoriju. Nepievieno tajā privātus attēlus.

## 2. Izvieto Render

1. Atver https://dashboard.render.com/ un pieslēdz GitHub kontu.
2. Izvēlies **New → Blueprint**, norādi savu repozitoriju un tā saknē esošo `render.yaml`.
3. Kad Render prasa `ADMIN_PASSWORD`, ieraksti savu stipru, unikālu paroli. Nedalies ar to ar spēlētājiem.
4. Apstiprini **Free** plānu un izvietošanu.
5. Kad izvietošana pabeigta, atver izsniegto `https://...onrender.com` saiti.

## 3. Pārbaudi demonstrāciju

- Spēlētāja ekrāns: `https://...onrender.com/`.
- Administrators: `https://...onrender.com/admin` (parole no 2. soļa).
- Administratora sadaļā **Komandas** paņem sešzīmju piekļuves kodus un iedod biedriem.
- No cita telefona pievienojies komandai un iesūti foto.
- Atver administratora sadaļu un apstiprini foto, lai pārbaudītu punktu tabulu.

## Svarīgi

- Render Free serveris pēc ~15 min bez pieprasījumiem aizmieg; pirmais pieprasījums var ielādēties ~1 minūti.
- Attēli šajā demonstrācijā tiek glabāti tikai uz pagaidu diska. Reāliem pasākumiem nepieciešama, piemēram, Supabase Storage un pastāvīga datubāze.
- Izvietojot vairākas instances vai darbinot vairākus procesus, šī SQLite versija nav piemērota.
- Pirms publicēšanas informē dalībniekus par foto glabāšanu un nelūdz iesniegt sensitīvus attēlus.
