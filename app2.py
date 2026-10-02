from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)

app.secret_key = "auto-servis-secret-key"

# =========================================================
# PUTANJA DO BAZE
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# INICIJALIZACIJA BAZE
# =========================================================

def init_db():

    conn = get_db()

    # -----------------------------------------------------
    # VOZILA
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marka TEXT NOT NULL,
            model TEXT NOT NULL,
            registracija TEXT UNIQUE NOT NULL,
            godiste INTEGER,
            kilometraza INTEGER,
            vlasnik TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # STARA SERVISNA ISTORIJA
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            datum TEXT NOT NULL,
            opis TEXT NOT NULL,
            cena REAL DEFAULT 0,
            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------------------
    # SERVISNI NALOZI
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS service_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            datum TEXT NOT NULL,
            problem TEXT,
            mehanicar_id INTEGER,
            mehanicar TEXT,
            delovi TEXT,
            cena_delova REAL DEFAULT 0,
            cena_rada REAL DEFAULT 0,
            ukupna_cena REAL DEFAULT 0,
            status TEXT DEFAULT 'Primljen',

            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------------------
    # MEHANIČARI
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mechanics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ime TEXT NOT NULL,
            prezime TEXT NOT NULL,
            telefon TEXT,
            specijalizacija TEXT
        )
    """)

    # -----------------------------------------------------
    # LAGER DELOVA
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv TEXT NOT NULL,
            proizvodjac TEXT,
            sifra TEXT,
            kolicina INTEGER DEFAULT 0,
            cena REAL DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # DELOVI U SERVISNOM NALOGU
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            kolicina INTEGER NOT NULL,
            cena REAL NOT NULL,

            FOREIGN KEY (order_id)
                REFERENCES service_orders(id)
                ON DELETE CASCADE,

            FOREIGN KEY (part_id)
                REFERENCES parts(id)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# MIGRACIJA POSTOJEĆE BAZE
# =========================================================

def migrate_database():

    conn = get_db()

    # =====================================================
    # SERVICE ORDERS
    # =====================================================

    columns = conn.execute("""
        PRAGMA table_info(service_orders)
    """).fetchall()

    column_names = {
        column["name"]
        for column in columns
    }

    if "problem" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN problem TEXT
        """)

    if "mehanicar_id" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN mehanicar_id INTEGER
        """)

    if "mehanicar" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN mehanicar TEXT
        """)

    if "delovi" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN delovi TEXT
        """)

    if "cena_delova" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN cena_delova REAL DEFAULT 0
        """)

    if "cena_rada" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN cena_rada REAL DEFAULT 0
        """)

    if "ukupna_cena" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN ukupna_cena REAL DEFAULT 0
        """)

    if "status" not in column_names:

        conn.execute("""
            ALTER TABLE service_orders
            ADD COLUMN status TEXT DEFAULT 'Primljen'
        """)

    # =====================================================
    # STARA KOLONA OPIS
    # =====================================================

    if "opis" in column_names:

        conn.execute("""
            UPDATE service_orders
            SET problem = opis
            WHERE
                (problem IS NULL OR problem = '')
                AND opis IS NOT NULL
        """)

    # =====================================================
    # PRAZAN STATUS
    # =====================================================

    conn.execute("""
        UPDATE service_orders
        SET status = 'Primljen'
        WHERE status IS NULL
           OR status = ''
    """)

    # =====================================================
    # MEHANIČARI
    # =====================================================

    mechanic_columns = conn.execute("""
        PRAGMA table_info(mechanics)
    """).fetchall()

    mechanic_column_names = {
        column["name"]
        for column in mechanic_columns
    }

    if "telefon" not in mechanic_column_names:

        conn.execute("""
            ALTER TABLE mechanics
            ADD COLUMN telefon TEXT
        """)

    if "specijalizacija" not in mechanic_column_names:

        conn.execute("""
            ALTER TABLE mechanics
            ADD COLUMN specijalizacija TEXT
        """)

    # =====================================================
    # PARTS
    # =====================================================

    part_columns = conn.execute("""
        PRAGMA table_info(parts)
    """).fetchall()

    part_column_names = {
        column["name"]
        for column in part_columns
    }

    if "proizvodjac" not in part_column_names:

        conn.execute("""
            ALTER TABLE parts
            ADD COLUMN proizvodjac TEXT
        """)

    if "sifra" not in part_column_names:

        conn.execute("""
            ALTER TABLE parts
            ADD COLUMN sifra TEXT
        """)

    if "kolicina" not in part_column_names:

        conn.execute("""
            ALTER TABLE parts
            ADD COLUMN kolicina INTEGER DEFAULT 0
        """)

    if "cena" not in part_column_names:

        conn.execute("""
            ALTER TABLE parts
            ADD COLUMN cena REAL DEFAULT 0
        """)

    conn.commit()
    conn.close()


# =========================================================
# POČETNA STRANICA
# =========================================================

@app.route("/")
def index():

    conn = get_db()

    vehicles = conn.execute("""
        SELECT *
        FROM vehicles
        ORDER BY id DESC
    """).fetchall()

    # Delovi sa malim lagerom
    low_stock_parts = conn.execute("""
        SELECT *
        FROM parts
        WHERE kolicina <= 5
        ORDER BY kolicina ASC, naziv ASC
    """).fetchall()

    # Broj vozila
    broj_vozila = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM vehicles
    """).fetchone()["broj"]

    # Broj servisnih naloga
    broj_naloga = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM service_orders
    """).fetchone()["broj"]

    # Broj mehaničara
    broj_mehanicara = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM mechanics
    """).fetchone()["broj"]

    # Broj delova
    broj_delova = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM parts
    """).fetchone()["broj"]

    conn.close()

    return render_template(
        "index.html",
        vehicles=vehicles,
        low_stock_parts=low_stock_parts,
        broj_vozila=broj_vozila,
        broj_naloga=broj_naloga,
        broj_mehanicara=broj_mehanicara,
        broj_delova=broj_delova
    )


# =========================================================
# DODAJ VOZILO
# =========================================================

@app.route("/dodaj-vozilo", methods=["GET", "POST"])
def dodaj_vozilo():

    if request.method == "POST":

        marka = request.form.get("marka", "").strip()
        model = request.form.get("model", "").strip()
        registracija = request.form.get(
            "registracija", ""
        ).strip()

        godiste = request.form.get(
            "godiste", ""
        ).strip()

        kilometraza = request.form.get(
            "kilometraza", ""
        ).strip()

        vlasnik = request.form.get(
            "vlasnik", ""
        ).strip()

        if not marka or not model or not registracija or not vlasnik:

            flash(
                "Popunite obavezna polja.",
                "error"
            )

            return redirect(
                url_for("dodaj_vozilo")
            )

        try:

            godiste_value = (
                int(godiste)
                if godiste
                else None
            )

            kilometraza_value = (
                int(kilometraza)
                if kilometraza
                else None
            )

        except ValueError:

            flash(
                "Godište i kilometraža moraju biti brojevi.",
                "error"
            )

            return redirect(
                url_for("dodaj_vozilo")
            )

        conn = get_db()

        try:

            conn.execute("""
                INSERT INTO vehicles
                (
                    marka,
                    model,
                    registracija,
                    godiste,
                    kilometraza,
                    vlasnik
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                marka,
                model,
                registracija,
                godiste_value,
                kilometraza_value,
                vlasnik
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            flash(
                "Vozilo sa tom registracijom već postoji.",
                "error"
            )

            return redirect(
                url_for("dodaj_vozilo")
            )

        conn.close()

        flash(
            "Vozilo je uspešno dodato.",
            "success"
        )

        return redirect(
            url_for("index")
        )

    return render_template(
        "dodaj_vozilo.html"
    )


# =========================================================
# IZMENI VOZILO
# =========================================================

@app.route(
    "/izmeni-vozilo/<int:vehicle_id>",
    methods=["GET", "POST"]
)
def izmeni_vozilo(vehicle_id):

    conn = get_db()

    vehicle = conn.execute("""
        SELECT *
        FROM vehicles
        WHERE id = ?
    """, (vehicle_id,)).fetchone()

    if not vehicle:

        conn.close()

        return "Vozilo nije pronađeno", 404

    if request.method == "POST":

        marka = request.form.get(
            "marka", ""
        ).strip()

        model = request.form.get(
            "model", ""
        ).strip()

        registracija = request.form.get(
            "registracija", ""
        ).strip()

        godiste = request.form.get(
            "godiste", ""
        ).strip()

        kilometraza = request.form.get(
            "kilometraza", ""
        ).strip()

        vlasnik = request.form.get(
            "vlasnik", ""
        ).strip()

        if not marka or not model or not registracija or not vlasnik:

            conn.close()

            flash(
                "Popunite sva obavezna polja.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_vozilo",
                    vehicle_id=vehicle_id
                )
            )

        try:

            godiste_value = (
                int(godiste)
                if godiste
                else None
            )

            kilometraza_value = (
                int(kilometraza)
                if kilometraza
                else None
            )

        except ValueError:

            conn.close()

            flash(
                "Godište i kilometraža moraju biti brojevi.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_vozilo",
                    vehicle_id=vehicle_id
                )
            )

        try:

            conn.execute("""
                UPDATE vehicles
                SET
                    marka = ?,
                    model = ?,
                    registracija = ?,
                    godiste = ?,
                    kilometraza = ?,
                    vlasnik = ?
                WHERE id = ?
            """, (
                marka,
                model,
                registracija,
                godiste_value,
                kilometraza_value,
                vlasnik,
                vehicle_id
            ))

            conn.commit()

        except sqlite3.IntegrityError:

            conn.close()

            flash(
                "Ta registracija već postoji.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_vozilo",
                    vehicle_id=vehicle_id
                )
            )

        conn.close()

        flash(
            "Vozilo je uspešno izmenjeno.",
            "success"
        )

        return redirect(
            url_for("index")
        )

    conn.close()

    return render_template(
        "izmeni_vozilo.html",
        vehicle=vehicle
    )


# =========================================================
# OBRIŠI VOZILO
# =========================================================

@app.route(
    "/obrisi-vozilo/<int:vehicle_id>",
    methods=["POST"]
)
def obrisi_vozilo(vehicle_id):

    conn = get_db()

    vehicle = conn.execute("""
        SELECT id
        FROM vehicles
        WHERE id = ?
    """, (vehicle_id,)).fetchone()

    if not vehicle:

        conn.close()

        flash(
            "Vozilo nije pronađeno.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    orders = conn.execute("""
        SELECT id
        FROM service_orders
        WHERE vehicle_id = ?
    """, (vehicle_id,)).fetchall()

    # Vraćanje delova na lager
    for order in orders:

        used_parts = conn.execute("""
            SELECT
                part_id,
                kolicina
            FROM order_parts
            WHERE order_id = ?
        """, (order["id"],)).fetchall()

        for part in used_parts:

            conn.execute("""
                UPDATE parts
                SET kolicina = kolicina + ?
                WHERE id = ?
            """, (
                part["kolicina"],
                part["part_id"]
            ))

        conn.execute("""
            DELETE FROM order_parts
            WHERE order_id = ?
        """, (order["id"],))

    conn.execute("""
        DELETE FROM services
        WHERE vehicle_id = ?
    """, (vehicle_id,))

    conn.execute("""
        DELETE FROM service_orders
        WHERE vehicle_id = ?
    """, (vehicle_id,))

    conn.execute("""
        DELETE FROM vehicles
        WHERE id = ?
    """, (vehicle_id,))

    conn.commit()
    conn.close()

    flash(
        "Vozilo je obrisano.",
        "success"
    )

    return redirect(
        url_for("index")
    )


# =========================================================
# STRANICA VOZILA / SERVIS
# =========================================================

@app.route("/vozilo/<int:vehicle_id>")
def vozilo(vehicle_id):

    conn = get_db()

    # -----------------------------------------------------
    # VOZILO
    # -----------------------------------------------------

    vehicle = conn.execute(
        """
        SELECT *
        FROM vehicles
        WHERE id = ?
        """,
        (vehicle_id,)
    ).fetchone()

    if vehicle is None:

        conn.close()

        return "Vozilo nije pronađeno", 404

    # -----------------------------------------------------
    # STARA SERVISNA ISTORIJA
    # -----------------------------------------------------

    services = conn.execute(
        """
        SELECT *
        FROM services
        WHERE vehicle_id = ?
        ORDER BY datum DESC, id DESC
        """,
        (vehicle_id,)
    ).fetchall()

    # -----------------------------------------------------
    # SERVISNI NALOZI
    # -----------------------------------------------------

    service_orders = conn.execute(
        """
        SELECT *
        FROM service_orders
        WHERE vehicle_id = ?
        ORDER BY id DESC
        """,
        (vehicle_id,)
    ).fetchall()

    # -----------------------------------------------------
    # MEHANIČARI
    # -----------------------------------------------------

    mechanics = conn.execute(
        """
        SELECT *
        FROM mechanics
        ORDER BY ime ASC, prezime ASC
        """
    ).fetchall()

    # -----------------------------------------------------
    # LAGER / DELOVI
    # -----------------------------------------------------

    parts = conn.execute(
        """
        SELECT *
        FROM parts
        ORDER BY naziv ASC
        """
    ).fetchall()

    # -----------------------------------------------------
    # DELOVI PO SERVISNOM NALOGU
    # -----------------------------------------------------

    order_parts = {}

    for order in service_orders:

        rows = conn.execute(
            """
            SELECT
                order_parts.id,
                order_parts.order_id,
                order_parts.part_id,
                order_parts.kolicina,
                order_parts.cena,
                parts.naziv,
                parts.proizvodjac,
                parts.sifra
            FROM order_parts
            JOIN parts
                ON parts.id = order_parts.part_id
            WHERE order_parts.order_id = ?
            ORDER BY order_parts.id ASC
            """,
            (order["id"],)
        ).fetchall()

        order_parts[order["id"]] = rows

    conn.close()

    return render_template(
        "servis.html",
        vehicle=vehicle,
        services=services,
        service_orders=service_orders,
        mechanics=mechanics,
        parts=parts,
        order_parts=order_parts
    )


# =========================================================
# DODAJ STARI SERVIS
# =========================================================

@app.route(
    "/dodaj-servis/<int:vehicle_id>",
    methods=["POST"]
)
def dodaj_servis(vehicle_id):

    datum = request.form.get(
        "datum",
        ""
    ).strip()

    opis = request.form.get(
        "opis",
        ""
    ).strip()

    cena_text = request.form.get(
        "cena",
        "0"
    ).strip()

    if not datum or not opis:

        flash(
            "Datum i opis servisa su obavezni.",
            "error"
        )

        return redirect(
            url_for(
                "vozilo",
                vehicle_id=vehicle_id
            )
        )

    try:

        cena = float(cena_text or 0)

        if cena < 0:
            cena = 0

    except ValueError:

        flash(
            "Cena nije ispravna.",
            "error"
        )

        return redirect(
            url_for(
                "vozilo",
                vehicle_id=vehicle_id
            )
        )

    conn = get_db()

    conn.execute("""
        INSERT INTO services
        (
            vehicle_id,
            datum,
            opis,
            cena
        )
        VALUES (?, ?, ?, ?)
    """, (
        vehicle_id,
        datum,
        opis,
        cena
    ))

    conn.commit()
    conn.close()

    flash(
        "Servis je dodat u istoriju.",
        "success"
    )

    return redirect(
        url_for(
            "vozilo",
            vehicle_id=vehicle_id
        )
    )


# =========================================================
# OBRIŠI STARI SERVIS
# =========================================================

@app.route(
    "/obrisi-servis/<int:service_id>",
    methods=["POST"]
)
def obrisi_servis(service_id):

    conn = get_db()

    service = conn.execute("""
        SELECT vehicle_id
        FROM services
        WHERE id = ?
    """, (service_id,)).fetchone()

    if not service:

        conn.close()

        return redirect(
            url_for("index")
        )

    vehicle_id = service["vehicle_id"]

    conn.execute("""
        DELETE FROM services
        WHERE id = ?
    """, (service_id,))

    conn.commit()
    conn.close()

    flash(
        "Servis je obrisan.",
        "success"
    )

    return redirect(
        url_for(
            "vozilo",
            vehicle_id=vehicle_id
        )
    )


# =========================================================
# DODAJ SERVISNI NALOG
# =========================================================

@app.route(
    "/dodaj-nalog/<int:vehicle_id>",
    methods=["POST"]
)
def dodaj_nalog(vehicle_id):

    datum = request.form.get(
        "datum",
        ""
    ).strip()

    problem = request.form.get(
        "problem",
        ""
    ).strip()

    mehanicar_id_text = request.form.get(
        "mehanicar_id",
        ""
    ).strip()

    status = request.form.get(
        "status",
        "Primljen"
    ).strip()

    cena_rada_text = request.form.get(
        "cena_rada",
        "0"
    ).strip()

    # -----------------------------------------------------
    # PROVERA VOZILA
    # -----------------------------------------------------

    conn = get_db()

    vehicle = conn.execute("""
        SELECT id
        FROM vehicles
        WHERE id = ?
    """, (vehicle_id,)).fetchone()

    if not vehicle:

        conn.close()

        flash(
            "Vozilo nije pronađeno.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    # -----------------------------------------------------
    # DATUM
    # -----------------------------------------------------

    if not datum:

        conn.close()

        flash(
            "Datum je obavezan.",
            "error"
        )

        return redirect(
            url_for(
                "vozilo",
                vehicle_id=vehicle_id
            )
        )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    dozvoljeni_statusi = [
        "Primljen",
        "U radu",
        "Završen",
        "Preuzet"
    ]

    if status not in dozvoljeni_statusi:

        status = "Primljen"

    # -----------------------------------------------------
    # CENA RADA
    # -----------------------------------------------------

    try:

        cena_rada = float(
            cena_rada_text or 0
        )

        if cena_rada < 0:
            cena_rada = 0

    except ValueError:

        conn.close()

        flash(
            "Cena rada nije ispravna.",
            "error"
        )

        return redirect(
            url_for(
                "vozilo",
                vehicle_id=vehicle_id
            )
        )

    # -----------------------------------------------------
    # MEHANIČAR
    # -----------------------------------------------------

    mehanicar_id = None
    mehanicar = ""

    if mehanicar_id_text:

        try:

            mehanicar_id = int(
                mehanicar_id_text
            )

        except ValueError:

            mehanicar_id = None

        if mehanicar_id:

            mechanic = conn.execute("""
                SELECT *
                FROM mechanics
                WHERE id = ?
            """, (mehanicar_id,)).fetchone()

            if mechanic:

                mehanicar = (
                    mechanic["ime"]
                    + " "
                    + mechanic["prezime"]
                )

                if mechanic["specijalizacija"]:

                    mehanicar += (
                        " - "
                        + mechanic["specijalizacija"]
                    )

            else:

                mehanicar_id = None
                mehanicar = ""

    # -----------------------------------------------------
    # DELOVI IZ FORME
    # -----------------------------------------------------

    part_ids = request.form.getlist(
        "part_id"
    )

    part_quantities = request.form.getlist(
        "part_kolicina"
    )

    selected_parts = []

    # -----------------------------------------------------
    # UČITAJ DELOVE
    # -----------------------------------------------------

    for index, part_id_text in enumerate(part_ids):

        if not part_id_text:
            continue

        try:

            part_id = int(
                part_id_text
            )

        except ValueError:

            continue

        try:

            quantity = int(
                part_quantities[index]
            )

        except (ValueError, IndexError):

            quantity = 0

        if quantity <= 0:
            continue

        part = conn.execute("""
            SELECT *
            FROM parts
            WHERE id = ?
        """, (part_id,)).fetchone()

        if not part:
            continue

        selected_parts.append({
            "id": part["id"],
            "naziv": part["naziv"],
            "kolicina": quantity,
            "cena": float(
                part["cena"] or 0
            ),
            "lager": int(
                part["kolicina"] or 0
            )
        })

    # -----------------------------------------------------
    # SABERI DUPLIKATE DELOVA
    # -----------------------------------------------------

    quantities_by_part = {}

    for item in selected_parts:

        part_id = item["id"]

        if part_id not in quantities_by_part:

            quantities_by_part[part_id] = 0

        quantities_by_part[part_id] += item["kolicina"]

    # -----------------------------------------------------
    # PROVERA LAGERA
    # -----------------------------------------------------

    for part_id, total_quantity in quantities_by_part.items():

        part = conn.execute("""
            SELECT *
            FROM parts
            WHERE id = ?
        """, (part_id,)).fetchone()

        if not part:
            continue

        lager = int(
            part["kolicina"] or 0
        )

        if total_quantity > lager:

            conn.close()

            flash(
                f"Nema dovoljno dela '{part['naziv']}' na lageru. "
                f"Na lageru je {lager}, "
                f"a traženo je {total_quantity}.",
                "error"
            )

            return redirect(
                url_for(
                    "vozilo",
                    vehicle_id=vehicle_id
                )
            )

    # -----------------------------------------------------
    # CENA DELOVA
    # -----------------------------------------------------

    cena_delova = 0

    for item in selected_parts:

        cena_delova += (
            item["kolicina"]
            *
            item["cena"]
        )

    # -----------------------------------------------------
    # UKUPNA CENA
    # -----------------------------------------------------

    ukupna_cena = (
        cena_delova
        +
        cena_rada
    )

    # -----------------------------------------------------
    # TEKST DELOVA
    # -----------------------------------------------------

    delovi_text = ""

    if selected_parts:

        delovi_text = ", ".join(
            [
                f"{item['naziv']} x {item['kolicina']}"
                for item in selected_parts
            ]
        )

    # -----------------------------------------------------
    # KREIRAJ NALOG
    # -----------------------------------------------------

    cursor = conn.execute("""
        INSERT INTO service_orders
        (
            vehicle_id,
            datum,
            problem,
            mehanicar_id,
            mehanicar,
            delovi,
            cena_delova,
            cena_rada,
            ukupna_cena,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        vehicle_id,
        datum,
        problem,
        mehanicar_id,
        mehanicar,
        delovi_text,
        cena_delova,
        cena_rada,
        ukupna_cena,
        status
    ))

    order_id = cursor.lastrowid

    # -----------------------------------------------------
    # UPIS DELOVA U ORDER_PARTS
    # -----------------------------------------------------

    for item in selected_parts:

        conn.execute("""
            INSERT INTO order_parts
            (
                order_id,
                part_id,
                kolicina,
                cena
            )
            VALUES (?, ?, ?, ?)
        """, (
            order_id,
            item["id"],
            item["kolicina"],
            item["cena"]
        ))

        # Skidanje sa lagera
        conn.execute("""
            UPDATE parts
            SET kolicina = kolicina - ?
            WHERE id = ?
        """, (
            item["kolicina"],
            item["id"]
        ))

    conn.commit()
    conn.close()

    flash(
        "Servisni nalog je uspešno kreiran.",
        "success"
    )

    return redirect(
        url_for(
            "vozilo",
            vehicle_id=vehicle_id
        )
    )


# =========================================================
# PROMENA STATUSA
# =========================================================

@app.route(
    "/promeni-status/<int:order_id>",
    methods=["POST"]
)
def promeni_status(order_id):

    status = request.form.get(
        "status",
        ""
    ).strip()

    dozvoljeni_statusi = [
        "Primljen",
        "U radu",
        "Završen",
        "Preuzet"
    ]

    if status not in dozvoljeni_statusi:

        flash(
            "Nepoznat status.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    conn = get_db()

    order = conn.execute("""
        SELECT vehicle_id
        FROM service_orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if not order:

        conn.close()

        flash(
            "Servisni nalog nije pronađen.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    vehicle_id = order["vehicle_id"]

    conn.execute("""
        UPDATE service_orders
        SET status = ?
        WHERE id = ?
    """, (
        status,
        order_id
    ))

    conn.commit()
    conn.close()

    flash(
        "Status servisnog naloga je promenjen.",
        "success"
    )

    return redirect(
        url_for(
            "vozilo",
            vehicle_id=vehicle_id
        )
    )


# =========================================================
# OBRIŠI SERVISNI NALOG
# =========================================================

@app.route(
    "/obrisi-nalog/<int:order_id>",
    methods=["POST"]
)
def obrisi_nalog(order_id):

    conn = get_db()

    order = conn.execute("""
        SELECT vehicle_id
        FROM service_orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if not order:

        conn.close()

        flash(
            "Servisni nalog nije pronađen.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    vehicle_id = order["vehicle_id"]

    # -----------------------------------------------------
    # VRATI DELOVE NA LAGER
    # -----------------------------------------------------

    used_parts = conn.execute("""
        SELECT
            part_id,
            kolicina
        FROM order_parts
        WHERE order_id = ?
    """, (order_id,)).fetchall()

    for item in used_parts:

        conn.execute("""
            UPDATE parts
            SET kolicina = kolicina + ?
            WHERE id = ?
        """, (
            item["kolicina"],
            item["part_id"]
        ))

    # -----------------------------------------------------
    # OBRIŠI DELOVE NALOGA
    # -----------------------------------------------------

    conn.execute("""
        DELETE FROM order_parts
        WHERE order_id = ?
    """, (order_id,))

    # -----------------------------------------------------
    # OBRIŠI NALOG
    # -----------------------------------------------------

    conn.execute("""
        DELETE FROM service_orders
        WHERE id = ?
    """, (order_id,))

    conn.commit()
    conn.close()

    flash(
        "Servisni nalog je obrisan, a delovi su vraćeni na lager.",
        "success"
    )

    return redirect(
        url_for(
            "vozilo",
            vehicle_id=vehicle_id
        )
    )


# =========================================================
# MEHANIČARI
# =========================================================

@app.route("/mehanicari")
def mehanicari():

    conn = get_db()

    mechanics = conn.execute("""
        SELECT *
        FROM mechanics
        ORDER BY ime ASC, prezime ASC
    """).fetchall()

    conn.close()

    return render_template(
        "mehanicari.html",
        mechanics=mechanics
    )


# =========================================================
# DODAJ MEHANIČARA
# =========================================================

@app.route(
    "/dodaj-mehanicara",
    methods=["POST"]
)
def dodaj_mehanicara():

    ime = request.form.get(
        "ime",
        ""
    ).strip()

    prezime = request.form.get(
        "prezime",
        ""
    ).strip()

    telefon = request.form.get(
        "telefon",
        ""
    ).strip()

    specijalizacija = request.form.get(
        "specijalizacija",
        ""
    ).strip()

    if not ime or not prezime:

        flash(
            "Ime i prezime su obavezni.",
            "error"
        )

        return redirect(
            url_for("mehanicari")
        )

    conn = get_db()

    conn.execute("""
        INSERT INTO mechanics
        (
            ime,
            prezime,
            telefon,
            specijalizacija
        )
        VALUES (?, ?, ?, ?)
    """, (
        ime,
        prezime,
        telefon,
        specijalizacija
    ))

    conn.commit()
    conn.close()

    flash(
        "Mehaničar je dodat.",
        "success"
    )

    return redirect(
        url_for("mehanicari")
    )


# =========================================================
# IZMENI MEHANIČARA
# =========================================================

@app.route(
    "/izmeni-mehanicara/<int:mechanic_id>",
    methods=["GET", "POST"]
)
def izmeni_mehanicara(mechanic_id):

    conn = get_db()

    mechanic = conn.execute("""
        SELECT *
        FROM mechanics
        WHERE id = ?
    """, (mechanic_id,)).fetchone()

    if not mechanic:

        conn.close()

        return "Mehaničar nije pronađen", 404

    if request.method == "POST":

        ime = request.form.get(
            "ime",
            ""
        ).strip()

        prezime = request.form.get(
            "prezime",
            ""
        ).strip()

        telefon = request.form.get(
            "telefon",
            ""
        ).strip()

        specijalizacija = request.form.get(
            "specijalizacija",
            ""
        ).strip()

        if not ime or not prezime:

            conn.close()

            flash(
                "Ime i prezime su obavezni.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_mehanicara",
                    mechanic_id=mechanic_id
                )
            )

        conn.execute("""
            UPDATE mechanics
            SET
                ime = ?,
                prezime = ?,
                telefon = ?,
                specijalizacija = ?
            WHERE id = ?
        """, (
            ime,
            prezime,
            telefon,
            specijalizacija,
            mechanic_id
        ))

        conn.commit()
        conn.close()

        flash(
            "Mehaničar je izmenjen.",
            "success"
        )

        return redirect(
            url_for("mehanicari")
        )

    conn.close()

    return render_template(
        "izmeni_mehanicara.html",
        mechanic=mechanic
    )


# =========================================================
# OBRIŠI MEHANIČARA
# =========================================================

@app.route(
    "/obrisi-mehanicara/<int:mechanic_id>",
    methods=["POST"]
)
def obrisi_mehanicara(mechanic_id):

    conn = get_db()

    used = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM service_orders
        WHERE mehanicar_id = ?
    """, (mechanic_id,)).fetchone()

    if used["broj"] > 0:

        conn.close()

        flash(
            "Ovaj mehaničar je već korišćen u servisnim nalozima i ne može biti obrisan.",
            "error"
        )

        return redirect(
            url_for("mehanicari")
        )

    conn.execute("""
        DELETE FROM mechanics
        WHERE id = ?
    """, (mechanic_id,))

    conn.commit()
    conn.close()

    flash(
        "Mehaničar je obrisan.",
        "success"
    )

    return redirect(
        url_for("mehanicari")
    )


# =========================================================
# LAGER - LISTA DELOVA
# =========================================================

@app.route("/delovi")
def delovi():

    conn = get_db()

    parts = conn.execute("""
        SELECT *
        FROM parts
        ORDER BY naziv ASC
    """).fetchall()

    conn.close()

    return render_template(
        "delovi.html",
        parts=parts
    )


# =========================================================
# DODAJ DEO
# =========================================================

@app.route(
    "/dodaj-deo",
    methods=["POST"]
)
def dodaj_deo():

    naziv = request.form.get(
        "naziv",
        ""
    ).strip()

    proizvodjac = request.form.get(
        "proizvodjac",
        ""
    ).strip()

    sifra = request.form.get(
        "sifra",
        ""
    ).strip()

    kolicina_text = request.form.get(
        "kolicina",
        "0"
    ).strip()

    cena_text = request.form.get(
        "cena",
        "0"
    ).strip()

    if not naziv:

        flash(
            "Naziv dela je obavezan.",
            "error"
        )

        return redirect(
            url_for("delovi")
        )

    try:

        kolicina = int(
            kolicina_text or 0
        )

        cena = float(
            cena_text or 0
        )

    except ValueError:

        flash(
            "Količina i cena moraju biti ispravne.",
            "error"
        )

        return redirect(
            url_for("delovi")
        )

    if kolicina < 0:
        kolicina = 0

    if cena < 0:
        cena = 0

    conn = get_db()

    conn.execute("""
        INSERT INTO parts
        (
            naziv,
            proizvodjac,
            sifra,
            kolicina,
            cena
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        naziv,
        proizvodjac,
        sifra,
        kolicina,
        cena
    ))

    conn.commit()
    conn.close()

    flash(
        "Deo je dodat u lager.",
        "success"
    )

    return redirect(
        url_for("delovi")
    )


# =========================================================
# IZMENI DEO
# =========================================================

@app.route(
    "/izmeni-deo/<int:part_id>",
    methods=["GET", "POST"]
)
def izmeni_deo(part_id):

    conn = get_db()

    part = conn.execute("""
        SELECT *
        FROM parts
        WHERE id = ?
    """, (part_id,)).fetchone()

    if not part:

        conn.close()

        return "Deo nije pronađen", 404

    if request.method == "POST":

        naziv = request.form.get(
            "naziv",
            ""
        ).strip()

        proizvodjac = request.form.get(
            "proizvodjac",
            ""
        ).strip()

        sifra = request.form.get(
            "sifra",
            ""
        ).strip()

        kolicina_text = request.form.get(
            "kolicina",
            "0"
        ).strip()

        cena_text = request.form.get(
            "cena",
            "0"
        ).strip()

        if not naziv:

            conn.close()

            flash(
                "Naziv dela je obavezan.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_deo",
                    part_id=part_id
                )
            )

        try:

            kolicina = int(
                kolicina_text or 0
            )

            cena = float(
                cena_text or 0
            )

        except ValueError:

            conn.close()

            flash(
                "Količina i cena nisu ispravne.",
                "error"
            )

            return redirect(
                url_for(
                    "izmeni_deo",
                    part_id=part_id
                )
            )

        if kolicina < 0:
            kolicina = 0

        if cena < 0:
            cena = 0

        conn.execute("""
            UPDATE parts
            SET
                naziv = ?,
                proizvodjac = ?,
                sifra = ?,
                kolicina = ?,
                cena = ?
            WHERE id = ?
        """, (
            naziv,
            proizvodjac,
            sifra,
            kolicina,
            cena,
            part_id
        ))

        conn.commit()
        conn.close()

        flash(
            "Deo je izmenjen.",
            "success"
        )

        return redirect(
            url_for("delovi")
        )

    conn.close()

    return render_template(
        "izmeni_deo.html",
        part=part
    )


# =========================================================
# OBRIŠI DEO
# =========================================================

@app.route(
    "/obrisi-deo/<int:part_id>",
    methods=["POST"]
)
def obrisi_deo(part_id):

    conn = get_db()

    used = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM order_parts
        WHERE part_id = ?
    """, (part_id,)).fetchone()

    if used["broj"] > 0:

        conn.close()

        flash(
            "Ovaj deo je već korišćen u servisnom nalogu i ne može biti obrisan.",
            "error"
        )

        return redirect(
            url_for("delovi")
        )

    conn.execute("""
        DELETE FROM parts
        WHERE id = ?
    """, (part_id,))

    conn.commit()
    conn.close()

    flash(
        "Deo je obrisan iz lagera.",
        "success"
    )

    return redirect(
        url_for("delovi")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    conn = get_db()

    # -----------------------------------------------------
    # BROJ VOZILA
    # -----------------------------------------------------

    broj_vozila = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM vehicles
    """).fetchone()["broj"]

    # -----------------------------------------------------
    # BROJ NALOGA
    # -----------------------------------------------------

    broj_naloga = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM service_orders
    """).fetchone()["broj"]

    # -----------------------------------------------------
    # BROJ MEHANIČARA
    # -----------------------------------------------------

    broj_mehanicara = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM mechanics
    """).fetchone()["broj"]

    # -----------------------------------------------------
    # BROJ DELOVA
    # -----------------------------------------------------

    broj_delova = conn.execute("""
        SELECT COUNT(*) AS broj
        FROM parts
    """).fetchone()["broj"]

    # -----------------------------------------------------
    # UKUPAN PRIHOD
    # -----------------------------------------------------

    rezultat = conn.execute("""
        SELECT
            COALESCE(
                SUM(ukupna_cena),
                0
            ) AS prihod
        FROM service_orders
        WHERE status IN ('Završen', 'Preuzet')
    """).fetchone()

    ukupan_prihod = rezultat["prihod"]

    # -----------------------------------------------------
    # POSLEDNJI NALOZI
    # -----------------------------------------------------

    latest_orders = conn.execute("""
        SELECT
            service_orders.*,
            vehicles.marka,
            vehicles.model,
            vehicles.registracija
        FROM service_orders
        JOIN vehicles
            ON vehicles.id = service_orders.vehicle_id
        ORDER BY service_orders.id DESC
        LIMIT 5
    """).fetchall()

    # -----------------------------------------------------
    # MALI LAGER
    # -----------------------------------------------------

    low_stock_parts = conn.execute("""
        SELECT *
        FROM parts
        WHERE kolicina <= 5
        ORDER BY kolicina ASC, naziv ASC
    """).fetchall()

    # -----------------------------------------------------
    # STATUSI
    # -----------------------------------------------------

    status_counts = {}

    for status in [
        "Primljen",
        "U radu",
        "Završen",
        "Preuzet"
    ]:

        row = conn.execute("""
            SELECT COUNT(*) AS broj
            FROM service_orders
            WHERE status = ?
        """, (status,)).fetchone()

        status_counts[status] = row["broj"]

    conn.close()

    return render_template(
        "dashboard.html",
        broj_vozila=broj_vozila,
        broj_naloga=broj_naloga,
        broj_mehanicara=broj_mehanicara,
        broj_delova=broj_delova,
        ukupan_prihod=ukupan_prihod,
        latest_orders=latest_orders,
        low_stock_parts=low_stock_parts,
        status_counts=status_counts
    )


# =========================================================
# POKRETANJE APLIKACIJE
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("AUTO SERVIS - POKRETANJE")
    print("=" * 60)
    print(f"Baza: {DATABASE}")
    print("=" * 60)

    init_db()
    migrate_database()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )