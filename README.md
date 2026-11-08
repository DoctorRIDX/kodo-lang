# ◆ Kodo

**Kodo** adalah bahasa pemrograman untuk **membuat aplikasi** (ekstensi file `.kd`), ditulis 100% dengan **Python** (tanpa library tambahan). Sintaksnya ringkas, ada layar/komponen, event, state, navigasi, import, dan blok `style` mirip CSS.

Kodo bisa jalan dalam 3 mode:

| Mode | Perintah | Keterangan |
|------|----------|------------|
| Terminal (TUI) | `kodo run app.kd` | aplikasi tampil di terminal, pilih tombol pakai nomor |
| Web | `kodo serve app.kd` | aplikasi tampil di browser (`http://127.0.0.1:8080`), lengkap dengan CSS dari blok `style` |
| Skrip | `kodo run skrip.kd` | kalau tidak ada `void.screen`, fungsi `main()` dijalankan |

## Instal (Termux / Acode terminal)

```sh
pkg update && pkg install -y python git
git clone https://github.com/DoctorRIDX/kodo-lang.git
cd kodo-lang
sh install.sh            # membuat perintah `kodo`
```

Tanpa instal juga bisa: `python -m kodo run examples/hello.kd`
Via pip: `pip install .`

## Mulai cepat

```sh
kodo run examples/counter.kd        # terminal
kodo serve examples/counter.kd      # buka http://127.0.0.1:8080
kodo new proyekku                   # buat proyek baru
kodo check app.kd                   # cek sintaks
kodo repl                           # interaktif
```

Kontrol di mode terminal: `nomor` = klik/isi, `h<nomor>` = tahan (onhold), `b` = kembali, `r` = segarkan, `q` = keluar.

## Referensi bahasa

### 1. Dasar

```kodo
// komentar
net nama = "Kodo"            // variabel
net umur = 17
net aktif = true             // Boolean: true/false (atau benar/salah)
net buah = ["apel", "jeruk"] // Array
net user = {"nama": "A"}     // Object, akses: user.nama
net hasil = (umur + 3) * 2 / 4 % 3
```

Operator: `+ - * / %`, perbandingan `== != > < >= <=`, logika `and or not` (juga `&& || !`, `dan atau bukan`), keanggotaan `in`.
String mendukung interpolasi: `"Halo {nama}"`. `+` pada string menggabungkan teks.

### 2. Kondisi

```kodo
if (umur >= 18) {
   print "dewasa"
} elseif (umur > 12) {
   print "remaja"
} else {
   print "anak"
}
if (umur > 5) then print "ok" else print "kecil"   // satu baris
```

### 3. Perulangan

```kodo
loop.3 { print "hai" }                // 3 kali
loop.i 5 { total += i }               // i = 1..5
loop.for b.buah { print b }           // tiap item (juga: loop.for b in buah)
break / continue
```

### 4. Fungsi

```kodo
void tambah(a, b) {
   return a + b
}
print tambah(2, 3)
```

Fungsi bawaan: `len str num int float upper lower trim round abs min max sum range push pop join split replace contains keys sort reverse type random randint now today file input toast back goto quit`.
Metode: `teks.upper()`, `list.push(x)`, `list.join(", ")`, dll.

### 5. Layar & komponen

```kodo
void.screen main {
   title  ; judul."Selamat datang"          // judul
   text   ; sapa."Hello"                    // teks      (id = sapa)
   image  ; logo "logo.png"                 // gambar
   nama   ; input("Nama kamu : ")           // input, nilainya masuk variabel `nama`
   button ; ok."Klik".onclick.active.simpan()
}
```

Format baris: `jenis ; id."nilai".event.aksi.fungsi()`. Jenis: `text title image button input link divider`.

### 6. Layout

```kodo
column {
   text ; a."Halo"
   row {
      button ; y."Ya".onclick.active.pilih()
      button ; n."Tidak".onclick.active.pilih()
   }
   list items {          // ulangi untuk setiap isi array `items`
      text item          // `item` dan `index` tersedia di dalam list
   }
}
```

Tersedia juga `box` / `card` (kotak dengan border). Di dalam layar boleh pakai `if`, `loop`, `net`.

### 7. Event & aksi

| Event | Arti |
|-------|------|
| `.onclick` | klik / tap |
| `.onhold` | tahan (long-press) |
| `.onchange` | isi input berubah (nilai dikirim ke fungsi kalau fungsi punya parameter) |

| Aksi | Arti |
|------|------|
| `.active.fn()` / `.aksi.fn()` | panggil fungsi `fn` |
| `.show.fn()` | panggil fungsi dan tampilkan hasilnya (toast) |
| `.show.id()` / `.makevisible.id()` | munculkan komponen ber-id `id` (otomatis tersembunyi di awal) |
| `.hide.id()` / `.remove.id()` | sembunyikan / hapus komponen |
| `.toggle.id()` | tampil/sembunyi |

`text ; nama."Halo ".show.fn()` → teks ditambah hasil `fn()` saat layar digambar.

### 8. State

```kodo
state count = 0                 // bernilai tetap antar-render
void tambah() { count = count + 1 }   // juga: count++ , count += 1
void.screen main {
   text ; t."count : {count}"
   button ; b."klik".onclick.active.tambah()
}
```

`net` di dalam layar bersifat lokal tiap render; pakai `state` untuk data yang harus bertahan.

### 9. Navigasi

```kodo
button ; kembali."Kembali".onclick.active.back()
button ; detail."Detail".onclick.active.halamandetail()   // nama screen = pindah layar
```

Layar pertama: `main` (atau `home`/`start`/`app`, kalau tidak ada: layar yang pertama ditulis).

### 10. Import

```kodo
import logo.png                       // aset gambar/font (disajikan oleh mode web)
import daftar-akun.txt                // file teks, bisa dicek: if (x in daftar-akun.txt)
import modul.kd                       // pakai kode dari file Kodo lain
import "https://fonts.googleapis.com/css2?family=Poppins"
```

### 11. Style (mirip CSS)

```kodo
void.screen style {
   pembuka ; {                   // selector = id komponen, atau jenis (text, button, ...), atau *
      font ; "https://fonts.googleapis.com/css2?family=Poppins"
      color ; #6d4aff            // #fffff yang kurang digit otomatis dilengkapi
      set.size ; 15px
      bold ; true
   }
   button ; {
      background ; #6d4aff
      radius ; 12
   }
}
```

Properti: `font color size(set.size) bg/background radius bold italic align padding margin width height shadow` (properti CSS lain juga diteruskan apa adanya). Nama warna: `merah hijau biru kuning putih hitam ungu oranye pink` dll. Di terminal, `color`, `background`, `bold`, `italic` ikut diterapkan.

## Struktur proyek

```
kodo/lexer.py    komentar + pohon blok { }
kodo/expr.py     ekspresi (tokenizer, parser, evaluator)
kodo/parser.py   statement, komponen, layout, style
kodo/interp.py   interpreter, state, event, navigasi, view tree
kodo/style.py    blok style -> CSS / warna terminal
kodo/term.py     UI terminal
kodo/web.py      server web (stdlib)
kodo/cli.py      perintah `kodo`
examples/        contoh program .kd
tests/           unit test:  python -m unittest discover -s tests
```

## Catatan & rencana

- Blok `{ ... }` ditulis multi-baris (belum ada blok satu baris selain `if ... then ... else ...`).
- Di format `jenis ; id."nilai"`, kata pertama setelah `;` dianggap id komponen.
- Rencana: export ke HTML statis, build APK, komponen tambahan (checkbox, dropdown), animasi.

Lisensi: MIT.
