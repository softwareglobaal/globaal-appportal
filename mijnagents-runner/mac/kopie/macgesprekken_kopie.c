/* MacGesprekkenKopie: het enige programma met Full Disk Access voor De WhatsApp-wacht en De Belwacht
   (ontwerp dagvaststelling v2.0, fase 2). Het leest vaste databanken met vaste vragen en schrijft alleen de toegelaten
   kolommen weg: wie, wanneer, hoeveel en hoe lang. Nooit berichttekst, media, status of voorbeeldtekst (Codex P1).
   Geen script, geen Python, geen omgevingsvariabelen, geen paden van buiten: de toestemming hangt aan de cdhash van
   dit programma; wie het vervangt, verliest de toegang.

       MacGesprekkenKopie whatsapp    berichten, oproepen en de betrokken contacten van WhatsApp
       MacGesprekkenKopie telefoon    oproepen van de iPhone en de contacten bij die nummers
       MacGesprekkenKopie sms         sms en iMessages uit Messages: per bericht gesprek, tijd, richting en dienst

   Venster: de laatste VENSTER_DAGEN dagen (de runner leest er hoogstens zestig van). De vragen lopen in een
   leestransactie over de bron, dus met de WAL erbij (Codex P2). Het resultaat staat eerst in het geheugen en gaat
   dan atomisch naar ~/Library/Caches/mijnagents/mac-gesprekken/<set>/gesprekken-<aanvraag>.sqlite (0600, map 0700):
   elke aanvraag haar eigen uitvoer (Codex R2). Daarna
   status.json met het tijdstip, de aanvraag-ID van de runner (uit het bestand aanvraag, alleen 32 hextekens) en de
   uitkomst per bron: ok, geweigerd, ontbreekt, onverwacht (ander schema) of fout. Geen inhoud, geen paden. */
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pwd.h>
#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sysexits.h>
#include <time.h>
#include <unistd.h>

#define VENSTER_DAGEN 62
#define APPLE_EPOCH 978307200.0   /* 1-1-2001 in Unix-tijd: Core Data telt van daar */
#define WA "Library/Group Containers/group.net.whatsapp.WhatsApp.shared/"
#define NORM(x) "substr(replace(replace(replace(replace(replace(replace(" x \
    ", '+', ''), ' ', ''), '-', ''), '(', ''), ')', ''), '.', ''), -9)"

typedef struct {
    const char *schema;   /* naam van de bron in de vragen */
    const char *pad;      /* onder de thuismap */
} Bron;

typedef struct {
    const char *naam;
    const Bron *bronnen;
    size_t aantal;
    const char *vragen;   /* %.0f is het begin van het venster in Core Data-seconden */
} Set;

static const Bron WHATSAPP[] = {
    {"chat", WA "ChatStorage.sqlite"},
    {"oproepen", WA "CallHistory.sqlite"},
    {"contacten", WA "ContactsV2.sqlite"},
};
static const Bron TELEFOON[] = {
    {"oproepen", "Library/Application Support/CallHistoryDB/CallHistory.storedata"},
    {"contacten", WA "ContactsV2.sqlite"},
};
static const Bron SMS[] = {
    {"berichten", "Library/Messages/chat.db"},
    {"contacten", WA "ContactsV2.sqlite"},
};

/* Alleen deze kolommen verlaten de bron. ZSTANZAID alleen van de melding van een oproep (soort 59): die wijst het
   gesprek van de oproep aan. Contacten alleen als ze bij een gesprek, oproep of nummer van het venster horen.
   Codex U1: wat de wachten niet tellen, verlaat de bron ook niet. Bij WhatsApp alleen gesprekken met een persoon of
   een groep (ZSESSIONTYPE 0 en 1; geen status, uitzendlijst of kanaal), bij de iPhone alleen gewone oproepen en
   FaceTime (geen WhatsApp of een andere app; van die alleen het tijdstip, om ze per venster te tellen). Zoals mac_gesprekken.PERSOON, GROEP en
   TEL_DIENSTEN. */
static const char WHATSAPP_VRAGEN[] =
    "CREATE TEMP TABLE toegelaten AS SELECT Z_PK FROM chat.ZWACHATSESSION WHERE ZSESSIONTYPE IN (0, 1);"
    "CREATE TABLE ZWAMESSAGE AS SELECT ZCHATSESSION, ZMESSAGEDATE, ZISFROMME, ZMESSAGETYPE, "
    "  CASE WHEN ZMESSAGETYPE = 59 THEN ZSTANZAID END AS ZSTANZAID FROM chat.ZWAMESSAGE WHERE ZMESSAGEDATE >= %.0f "
    "  AND ZCHATSESSION IN (SELECT Z_PK FROM temp.toegelaten);"
    "CREATE TABLE ZWACDCALLEVENT AS SELECT Z_PK, ZCALLIDSTRING, ZDATE, ZDURATION, Z1CALLEVENTS, "
    "  ZGROUPCALLCREATORUSERJIDSTRING, ZGROUPJIDSTRING FROM oproepen.ZWACDCALLEVENT WHERE ZDATE >= %.0f;"
    "CREATE TABLE ZWAAGGREGATECALLEVENT AS SELECT Z_PK, ZINCOMING, ZMISSED, ZVIDEO FROM oproepen.ZWAAGGREGATECALLEVENT "
    "  WHERE Z_PK IN (SELECT Z1CALLEVENTS FROM main.ZWACDCALLEVENT);"
    "CREATE TABLE ZWACDCALLEVENTPARTICIPANT AS SELECT Z_PK, Z1PARTICIPANTS, ZJIDSTRING "
    "  FROM oproepen.ZWACDCALLEVENTPARTICIPANT WHERE Z1PARTICIPANTS IN (SELECT Z_PK FROM main.ZWACDCALLEVENT);"
    "CREATE TEMP TABLE adressen AS SELECT ZJIDSTRING AS jid FROM main.ZWACDCALLEVENTPARTICIPANT "
    "  UNION SELECT ZGROUPCALLCREATORUSERJIDSTRING FROM main.ZWACDCALLEVENT UNION SELECT ZGROUPJIDSTRING FROM main.ZWACDCALLEVENT;"
    "CREATE TABLE ZWACHATSESSION AS SELECT Z_PK, ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE FROM chat.ZWACHATSESSION "
    "  WHERE ZSESSIONTYPE IN (0, 1) "
    "  AND (Z_PK IN (SELECT ZCHATSESSION FROM main.ZWAMESSAGE) OR ZCONTACTJID IN (SELECT jid FROM temp.adressen));"
    "INSERT INTO temp.adressen SELECT ZCONTACTJID FROM main.ZWACHATSESSION;"
    "CREATE TABLE ZWAADDRESSBOOKCONTACT AS SELECT Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER "
    "  FROM contacten.ZWAADDRESSBOOKCONTACT WHERE COALESCE(ZFULLNAME, '') != '' "
    "  AND (ZWHATSAPPID IN (SELECT jid FROM temp.adressen) OR ZLID IN (SELECT jid FROM temp.adressen));"
    "CREATE TABLE META AS SELECT 'nieuwste' AS sleutel, (SELECT MAX(ZMESSAGEDATE) FROM chat.ZWAMESSAGE "
    "  WHERE ZCHATSESSION IN (SELECT Z_PK FROM temp.toegelaten)) AS waarde;";

static const char TELEFOON_VRAGEN[] =
    "CREATE TABLE ZCALLRECORD AS SELECT ZUNIQUE_ID, ZDATE, ZDURATION, ZORIGINATED, ZANSWERED, ZADDRESS, "
    "  ZSERVICE_PROVIDER FROM oproepen.ZCALLRECORD WHERE ZDATE >= %.0f "
    "  AND ZSERVICE_PROVIDER IN ('com.apple.Telephony', 'com.apple.FaceTime');"
    "CREATE TEMP TABLE nummers AS SELECT DISTINCT " NORM("ZADDRESS") " AS n FROM main.ZCALLRECORD "
    "  WHERE length(ZADDRESS) >= 6;"
    "CREATE TABLE ZWAADDRESSBOOKCONTACT AS SELECT Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER "
    "  FROM contacten.ZWAADDRESSBOOKCONTACT WHERE COALESCE(ZFULLNAME, '') != '' "
    "  AND " NORM("ZPHONENUMBER") " IN (SELECT n FROM temp.nummers);"
    "CREATE TABLE ANDERE_APPS AS SELECT ZDATE FROM oproepen.ZCALLRECORD WHERE ZDATE >= %.0f "
    "  AND COALESCE(ZSERVICE_PROVIDER, '') NOT IN ('com.apple.Telephony', 'com.apple.FaceTime');"
    "CREATE TABLE META AS SELECT 'nieuwste' AS sleutel, (SELECT MAX(ZDATE) FROM oproepen.ZCALLRECORD "
    "  WHERE ZSERVICE_PROVIDER IN ('com.apple.Telephony', 'com.apple.FaceTime')) AS waarde;";

/* Sms en iMessage (31-10-2026): nooit de kolommen text of attributedBody, geen bijlagen. Alleen gewone berichten
   (item_type 0) zonder reactie (associated_message_type 0). Messages bewaart de tijd in nanoseconden sinds 2001
   (vroeger in seconden); de kopie zet ze om naar seconden, zoals Core Data. Contacten alleen bij de nummers van het
   venster, zoals bij de telefoon. */
#define SMS_TIJD "(CASE WHEN m.date > 1000000000000 THEN m.date / 1000000000.0 ELSE m.date END)"
static const char SMS_VRAGEN[] =
    "CREATE TABLE BERICHT AS SELECT j.chat_id AS gesprek, " SMS_TIJD " AS datum, m.is_from_me AS van_mij, "
    "  m.service AS dienst FROM berichten.message m JOIN berichten.chat_message_join j ON j.message_id = m.ROWID "
    "  WHERE COALESCE(m.item_type, 0) = 0 AND COALESCE(m.associated_message_type, 0) = 0 "
    "  AND (m.date >= %.0f * 1000000000.0 OR (m.date < 1000000000000 AND m.date >= %.0f));"
    "CREATE TABLE GESPREK AS SELECT ROWID AS pk, chat_identifier AS ident, style AS soort, display_name AS naam "
    "  FROM berichten.chat WHERE ROWID IN (SELECT gesprek FROM main.BERICHT);"
    "CREATE TABLE DEELNEMER AS SELECT j.chat_id AS gesprek, h.id AS adres FROM berichten.chat_handle_join j "
    "  JOIN berichten.handle h ON h.ROWID = j.handle_id WHERE j.chat_id IN (SELECT pk FROM main.GESPREK);"
    "CREATE TEMP TABLE nummers AS SELECT DISTINCT " NORM("adres") " AS n FROM main.DEELNEMER "
    "  WHERE length(adres) >= 6 AND instr(adres, '@') = 0;"
    "CREATE TABLE ZWAADDRESSBOOKCONTACT AS SELECT Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER "
    "  FROM contacten.ZWAADDRESSBOOKCONTACT WHERE COALESCE(ZFULLNAME, '') != '' "
    "  AND " NORM("ZPHONENUMBER") " IN (SELECT n FROM temp.nummers);"
    "CREATE TABLE META AS SELECT 'nieuwste' AS sleutel, (SELECT MAX(" SMS_TIJD ") FROM berichten.message m "
    "  WHERE COALESCE(m.item_type, 0) = 0) AS waarde;";

static const Set SETS[] = {
    {"whatsapp", WHATSAPP, sizeof WHATSAPP / sizeof *WHATSAPP, WHATSAPP_VRAGEN},
    {"telefoon", TELEFOON, sizeof TELEFOON / sizeof *TELEFOON, TELEFOON_VRAGEN},
    {"sms", SMS, sizeof SMS / sizeof *SMS, SMS_VRAGEN},
};

/* Een map onder dirfd openen zonder symlink te volgen; maak ze aan (0700) als dat mag. eigen: de map moet van
   deze gebruiker zijn en alleen voor hem (0700). */
static int map_open(int dirfd, const char *naam, int maak, int eigen) {
    if (maak && mkdirat(dirfd, naam, 0700) != 0 && errno != EEXIST) return -1;
    int fd = openat(dirfd, naam, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode) || st.st_uid != getuid() ||
        (st.st_mode & (S_IWGRP | S_IWOTH)) != 0 || (eigen && (st.st_mode & 0077) != 0)) {
        close(fd);
        errno = EPERM;
        return -1;
    }
    return fd;
}

/* De bron openen langs het pad onder de thuismap, map per map zonder een symlink te volgen, en zijn identiteit
   (apparaat en inode) in *id zetten. Een weigering van macOS is EPERM. Geeft 0, anders een errno. */
static int bron_identiteit(const char *home, const char *pad, struct stat *id) {
    char deel[PATH_MAX];
    if (snprintf(deel, sizeof deel, "%s", pad) >= (int)sizeof deel) return ENAMETOOLONG;
    int fd = open(home, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) return errno;
    char *rest = deel, *stuk;
    while ((stuk = strsep(&rest, "/")) != NULL) {
        if (!*stuk) continue;
        struct stat st;
        if (fstatat(fd, stuk, &st, AT_SYMLINK_NOFOLLOW) != 0) {
            int e = errno;
            close(fd);
            return e;
        }
        if (S_ISLNK(st.st_mode)) {
            close(fd);
            return ELOOP;
        }
        if (rest == NULL) {
            int bron = openat(fd, stuk, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
            int e = errno;
            close(fd);
            if (bron < 0) return e;
            int goed = fstat(bron, id) == 0 && S_ISREG(id->st_mode);
            close(bron);
            return goed ? 0 : EINVAL;
        }
        int volgend = openat(fd, stuk, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        int e = errno;
        close(fd);
        if (volgend < 0) return e;
        fd = volgend;
    }
    close(fd);
    return ENOENT;
}

/* Codex Q3: leest SQLite precies het bestand dat hierboven gecontroleerd werd? Het begin van unixFile (os_unix.c:
   methoden, vfs, inode, bestandsdescriptor) is sinds jaren gelijk; klopt het niet, dan faalt de vergelijking en
   leest de helper niets (veilig dicht). */
typedef struct {
    const void *methoden;
    void *vfs;
    void *inode;
    int h;
} UnixBestand;

static int zelfde_bestand(sqlite3 *db, const char *schema, const struct stat *id) {
    sqlite3_file *f = NULL;
    if (sqlite3_file_control(db, schema, SQLITE_FCNTL_FILE_POINTER, &f) != SQLITE_OK || f == NULL || f->pMethods == NULL)
        return 0;
    int h = ((const UnixBestand *)f)->h;
    struct stat st;
    return h >= 0 && fstat(h, &st) == 0 && st.st_dev == id->st_dev && st.st_ino == id->st_ino;
}

static const char *uit_errno(int e) {
    if (e == ENOENT) return "ontbreekt";
    if (e == EPERM || e == EACCES) return "geweigerd";
    if (e == ELOOP) return "onverwacht";
    return "fout";
}

/* Een pad als URI (file:...?mode=ro): elk teken buiten [A-Za-z0-9/._~-] als %XX. Zonder -wal naast de databank
   (de app is gesloten en heeft alles teruggeschreven) staat alles in het bestand zelf; dan immutable, want alleen
   lezend kan SQLite de -shm niet aanmaken. */
static int als_uri(const char *pad, int zonder_wal, char *uit, size_t ruimte) {
    static const char hex[] = "0123456789ABCDEF";
    size_t n = (size_t)snprintf(uit, ruimte, "file:");
    for (const unsigned char *p = (const unsigned char *)pad; *p; p++) {
        int gewoon = (*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') ||
                     strchr("/._~-", *p) != NULL;
        if (n + 4 >= ruimte) return 0;
        if (gewoon) {
            uit[n++] = (char)*p;
        } else {
            uit[n++] = '%';
            uit[n++] = hex[*p >> 4];
            uit[n++] = hex[*p & 15];
        }
    }
    return snprintf(uit + n, ruimte - n, zonder_wal ? "?mode=ro&immutable=1" : "?mode=ro") < (int)(ruimte - n);
}

/* Schrijf buf atomisch als naam in dirfd: eerst een nieuw tijdelijk bestand (O_EXCL, O_NOFOLLOW), dan rename. */
static int schrijf(int dirfd, const char *naam, const unsigned char *buf, size_t n) {
    char tijdelijk[NAME_MAX];
    if (snprintf(tijdelijk, sizeof tijdelijk, ".%s.%d.tmp", naam, (int)getpid()) >= (int)sizeof tijdelijk) return 0;
    unlinkat(dirfd, tijdelijk, 0);
    int fd = openat(dirfd, tijdelijk, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return 0;
    size_t gedaan = 0;
    while (gedaan < n) {
        ssize_t w = write(fd, buf + gedaan, n - gedaan);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) break;
        gedaan += (size_t)w;
    }
    int goed = gedaan == n && fsync(fd) == 0;
    goed = close(fd) == 0 && goed;
    if (goed && renameat(dirfd, tijdelijk, dirfd, naam) == 0) return 1;
    unlinkat(dirfd, tijdelijk, 0);
    return 0;
}

/* Wat een vroegere ronde liet liggen (een uitvoer die niemand las, of die een runner niet meer wiste), na tien minuten
   weg: nooit ouder dan dat staan er namen in de map. */
/* Codex S2: alleen de eigen uitvoernamen: gesprekken.sqlite, gesprekken-<aanvraag>.sqlite en .lezen-<aanvraag>.sqlite. */
static int is_uitvoer(const char *naam) {
    if (strcmp(naam, "gesprekken.sqlite") == 0) return 1;
    const char *rest = strncmp(naam, "gesprekken-", 11) == 0 ? naam + 11 : strncmp(naam, ".lezen-", 7) == 0 ? naam + 7 : NULL;
    if (rest == NULL || strlen(rest) != 32 + 7 || strcmp(rest + 32, ".sqlite") != 0) return 0;
    for (int i = 0; i < 32; i++)
        if (!((rest[i] >= '0' && rest[i] <= '9') || (rest[i] >= 'a' && rest[i] <= 'f'))) return 0;
    return 1;
}

static void ruim_op(int dirfd) {
    int kopie = dup(dirfd);
    DIR *d = kopie >= 0 ? fdopendir(kopie) : NULL;
    if (d == NULL) {
        if (kopie >= 0) close(kopie);
        return;
    }
    struct dirent *e;
    time_t grens = time(NULL) - 600;
    while ((e = readdir(d)) != NULL) {
        struct stat st;
        if (is_uitvoer(e->d_name) && fstatat(dirfd, e->d_name, &st, AT_SYMLINK_NOFOLLOW) == 0 && st.st_mtime < grens)
            unlinkat(dirfd, e->d_name, 0);
    }
    closedir(d);
}

/* De aanvraag-ID die de runner net voor zijn vraag schreef: precies 32 kleine hextekens, anders leeg. */
static void lees_aanvraag(int dirfd, char aanvraag[33]) {
    aanvraag[0] = 0;
    int fd = openat(dirfd, "aanvraag", O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return;
    char buf[40];
    ssize_t n = read(fd, buf, sizeof buf);
    close(fd);
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) n--;
    if (n != 32) return;
    for (int i = 0; i < 32; i++)
        if (!((buf[i] >= '0' && buf[i] <= '9') || (buf[i] >= 'a' && buf[i] <= 'f'))) return;
    memcpy(aanvraag, buf, 32);
    aanvraag[32] = 0;
}

int main(int argc, char *argv[]) {
    const Set *set = NULL;
    for (size_t i = 0; argc == 2 && i < sizeof SETS / sizeof *SETS; i++)
        if (strcmp(argv[1], SETS[i].naam) == 0) set = &SETS[i];
    if (set == NULL) {
        fprintf(stderr, "Gebruik: MacGesprekkenKopie whatsapp|telefoon|sms\n");
        return EX_USAGE;
    }
    umask(0077);
#ifdef BASIS_TEST
    /* Alleen de testbouw (tests/test_mac_gesprekken.py) leest onder een proefmap; de echte bouw nooit. */
    const char *home = BASIS_TEST;
#else
    struct passwd *wie = getpwuid(getuid());
    if (wie == NULL || wie->pw_dir == NULL || wie->pw_dir[0] != '/') {
        fprintf(stderr, "MacGesprekkenKopie: gebruiker onbekend\n");
        return EX_CONFIG;
    }
    const char *home = wie->pw_dir;
#endif
    int fd = open(home, O_RDONLY | O_DIRECTORY | O_CLOEXEC), volgend;
    const char *stappen[] = {"Library", "Caches", "mijnagents", "mac-gesprekken", set->naam};
    for (size_t i = 0; fd >= 0 && i < sizeof stappen / sizeof *stappen; i++) {
        volgend = map_open(fd, stappen[i], i >= 2, i >= 3);
        close(fd);
        fd = volgend;
    }
    if (fd < 0) {
        fprintf(stderr, "MacGesprekkenKopie: privemap niet veilig of niet te maken\n");
        return EX_CANTCREAT;
    }
    char aanvraag[33], uitnaam[64];
    lees_aanvraag(fd, aanvraag);
    snprintf(uitnaam, sizeof uitnaam, aanvraag[0] ? "gesprekken-%s.sqlite" : "gesprekken.sqlite", aanvraag);
    ruim_op(fd);
    unlinkat(fd, uitnaam, 0);   /* een oude uitvoer met deze naam blijft nooit staan als de nieuwe niet lukt */

    const char *uitkomst[8] = {0};
    const char *geheel = "ok";
    sqlite3 *db = NULL;
    if (sqlite3_open_v2(":memory:", &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_URI |
                        SQLITE_OPEN_NOFOLLOW, NULL) != SQLITE_OK) geheel = "fout";
    if (db) sqlite3_busy_timeout(db, 15000);
    for (size_t i = 0; i < set->aantal; i++) {
        char pad[PATH_MAX], wal[PATH_MAX + 8], uri[3 * PATH_MAX], sql[256];
        struct stat st, id;
        uitkomst[i] = "ok";
        if (snprintf(pad, sizeof pad, "%s/%s", home, set->bronnen[i].pad) >= (int)sizeof pad ||
            snprintf(wal, sizeof wal, "%s-wal", pad) >= (int)sizeof wal ||
            !als_uri(pad, lstat(wal, &st) != 0 && errno == ENOENT, uri, sizeof uri)) {
            uitkomst[i] = "fout";
        } else if ((errno = bron_identiteit(home, set->bronnen[i].pad, &id)) != 0) {
            uitkomst[i] = uit_errno(errno);
        } else {
#ifdef BASIS_TEST
            /* Alleen de testbouw: <bron>.wissel neemt hier de plaats van de gecontroleerde bron in (de race van Q3). */
            char wissel[PATH_MAX + 16];
            snprintf(wissel, sizeof wissel, "%s.wissel", pad);
            rename(wissel, pad);
#endif
            snprintf(sql, sizeof sql, "ATTACH ?1 AS %s", set->bronnen[i].schema);
            sqlite3_stmt *stmt = NULL;
            int rc = db ? sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) : SQLITE_ERROR;
            if (rc == SQLITE_OK) rc = sqlite3_bind_text(stmt, 1, uri, -1, SQLITE_TRANSIENT);
            if (rc == SQLITE_OK) rc = sqlite3_step(stmt) == SQLITE_DONE ? SQLITE_OK : sqlite3_errcode(db);
            sqlite3_finalize(stmt);
            if (rc != SQLITE_OK)
                uitkomst[i] = rc == SQLITE_AUTH || rc == SQLITE_PERM ? "geweigerd" : "fout";
            else if (!zelfde_bestand(db, set->bronnen[i].schema, &id))
                uitkomst[i] = "onverwacht";   /* het pad wees intussen naar een ander bestand */
        }
        if (strcmp(uitkomst[i], "ok") != 0 && strcmp(geheel, "geweigerd") != 0)
            geheel = uitkomst[i];
    }

    unsigned char *buf = NULL;
    sqlite3_int64 n = 0;
    if (strcmp(geheel, "ok") == 0) {
        char vragen[sizeof WHATSAPP_VRAGEN + sizeof TELEFOON_VRAGEN + sizeof SMS_VRAGEN + 64];
        double begin = (double)time(NULL) - APPLE_EPOCH - VENSTER_DAGEN * 86400.0;
        snprintf(vragen, sizeof vragen, set->vragen, begin, begin);
        /* Een leestransactie over alle bronnen: een samenhangend beeld, met de WAL erbij. Een vraag die faalt, wijst
           op een ander schema (een tabel of kolom die er niet meer is): onverwacht, nooit een halve kopie. */
        /* Codex Q4: de uitvoer zelf draagt de aanvraag-ID, zodat de runner een kopie van een andere start herkent. */
        char merk[96];
        snprintf(merk, sizeof merk, "INSERT INTO META VALUES('aanvraag', '%s');", aanvraag);
        int rc = sqlite3_exec(db, "BEGIN", NULL, NULL, NULL);
        if (rc == SQLITE_OK) rc = sqlite3_exec(db, vragen, NULL, NULL, NULL);
        if (rc == SQLITE_OK) rc = sqlite3_exec(db, merk, NULL, NULL, NULL);
        int fout = rc != SQLITE_OK ? sqlite3_errcode(db) : SQLITE_OK;
        sqlite3_exec(db, rc == SQLITE_OK ? "COMMIT" : "ROLLBACK", NULL, NULL, NULL);
        if (rc != SQLITE_OK) {
            geheel = fout == SQLITE_AUTH || fout == SQLITE_PERM ? "geweigerd" : fout == SQLITE_ERROR ? "onverwacht" : "fout";
        } else {
            for (size_t i = 0; i < set->aantal; i++) {
                char sql[64];
                snprintf(sql, sizeof sql, "DETACH %s", set->bronnen[i].schema);
                sqlite3_exec(db, sql, NULL, NULL, NULL);
            }
            sqlite3_exec(db, "DROP TABLE IF EXISTS temp.adressen; DROP TABLE IF EXISTS temp.nummers; "
                             "DROP TABLE IF EXISTS temp.toegelaten", NULL, NULL, NULL);
            buf = sqlite3_serialize(db, "main", &n, 0);
            if (buf == NULL || n < 100 || !schrijf(fd, uitnaam, buf, (size_t)n)) geheel = "fout";
        }
    }
    sqlite3_free(buf);
    sqlite3_close(db);

    char status[1024];
    int lengte = snprintf(status, sizeof status,
                          "{\"ts\": %lld, \"set\": \"%s\", \"aanvraag\": \"%s\", \"uitkomst\": \"%s\", \"bronnen\": {",
                          (long long)time(NULL), set->naam, aanvraag, geheel);
    for (size_t i = 0; i < set->aantal && lengte < (int)sizeof status; i++)
        lengte += snprintf(status + lengte, sizeof status - (size_t)lengte, "%s\"%s\": \"%s\"", i ? ", " : "",
                           set->bronnen[i].schema, uitkomst[i]);
    if (lengte < (int)sizeof status)
        lengte += snprintf(status + lengte, sizeof status - (size_t)lengte, "}}\n");
    int bewaard = lengte < (int)sizeof status && schrijf(fd, "status.json", (const unsigned char *)status, (size_t)lengte);
    close(fd);
    fputs(status, stdout);
    if (!bewaard) return EX_IOERR;
    return strcmp(geheel, "ok") == 0 ? 0 : strcmp(geheel, "geweigerd") == 0 ? 2 : 1;
}
