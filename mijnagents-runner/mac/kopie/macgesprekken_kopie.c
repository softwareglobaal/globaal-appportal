/* MacGesprekkenKopie: het enige programma met Full Disk Access voor De WhatsApp-wacht en De Belwacht
   (ontwerp dagvaststelling v2.0, fase 2). Het leest vaste databanken met vaste vragen en schrijft alleen de toegelaten
   kolommen weg: wie, wanneer, hoeveel en hoe lang. Nooit berichttekst, media, status of voorbeeldtekst (Codex P1).
   Geen script, geen Python, geen omgevingsvariabelen, geen paden van buiten: de toestemming hangt aan de cdhash van
   dit programma; wie het vervangt, verliest de toegang.

       MacGesprekkenKopie whatsapp    berichten, oproepen en de betrokken contacten van WhatsApp
       MacGesprekkenKopie telefoon    oproepen van de iPhone en de contacten bij die nummers
       MacGesprekkenKopie sms         sms en iMessages uit Messages: per bericht gesprek, tijd, richting en dienst
       MacGesprekkenKopie browser     de geschiedenis van Chrome, Edge, Firefox en Safari: per bezoek de tijd en de
                                      naam van de site; alleen bij een YouTube-video ook video-ID, titel en duur

   Sinds 01-11-2026 (T-0120 VOL-11, een nieuwe helper en een moment voor Mehdi): bij telefoon en sms ook het adresboek
   van Contacts (TEL-9: alleen naam en nummer, alleen bij een nummer van het venster) en de set browser (YT-1, WEB-1),
   zodat geen Python Full Disk Access nodig heeft. Die extra bronnen lezen een voor een, na de vaste bronnen: een extra
   bron die ontbreekt, geweigerd wordt of een ander schema heeft, laat de rest van de set werken; haar uitkomst staat in
   status.json onder "extra", nooit onder "bronnen".

   Venster: de laatste VENSTER_DAGEN dagen (de runner leest er hoogstens zestig van). De vragen lopen in een
   leestransactie over de bron, dus met de WAL erbij (Codex P2). Het resultaat staat eerst in het geheugen en gaat
   dan atomisch naar ~/Library/Caches/mijnagents/mac-gesprekken/<set>/gesprekken-<aanvraag>.sqlite (0600, map 0700):
   elke aanvraag haar eigen uitvoer (Codex R2). Daarna
   status.json met het tijdstip, de aanvraag-ID van de runner (uit het bestand aanvraag, alleen 32 hextekens) en de
   uitkomst per bron: ok, geweigerd, ontbreekt, onverwacht (ander schema) of fout. Geen inhoud, geen paden. */
#include <ctype.h>
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
/* TEL-9 (Codex 01-11): voor Contacts het volle internationale nummer, niet de laatste negen cijfers: anders kan een
   contact met hetzelfde nummer in een ander land meekomen. Zoals mac_gesprekken.nummer_sleutel: 00 vooraan weg, een 0
   vooraan wordt 32; zonder landnummer (hoogstens negen cijfers) ook 32. */
#define CIJFERS(x) "replace(replace(replace(replace(replace(replace(replace(replace(" x \
    ", '+', ''), ' ', ''), '-', ''), '(', ''), ')', ''), '.', ''), '/', ''), char(160), '')"
#define INTL(x) "(CASE WHEN " CIJFERS(x) " LIKE '00%%' THEN substr(" CIJFERS(x) ", 3) WHEN " CIJFERS(x) \
    " LIKE '0%%' THEN '32' || substr(" CIJFERS(x) ", 2) WHEN length(" CIJFERS(x) ") <= 9 THEN '32' || " \
    CIJFERS(x) " ELSE " CIJFERS(x) " END)"

typedef struct {
    const char *schema;   /* naam van de bron in de vragen */
    const char *pad;      /* onder de thuismap */
} Bron;

typedef struct {
    const char *naam;      /* in status.json en in de tabel BRON: adresboek, Chrome, Edge, Firefox, Safari */
    const char *map;       /* onder de thuismap */
    const char *bestand;   /* de databank in map, of met profielen in elke submap van map */
    int profielen;         /* 1: een databank per submap (een profiel van de browser, een bron van het adresboek) */
    int kopie;             /* 1: eerst een eigen kopie, want de browser houdt zijn geschiedenis open en vergrendeld */
    const char *vraag;     /* een INSERT; :begin is het begin van het venster in Unix-seconden, :pk en :browser */
} Extra;

typedef struct {
    const char *naam;
    const Bron *bronnen;
    size_t aantal;
    const char *vragen;   /* %.0f is het begin van het venster in Core Data-seconden */
    const Extra *extra;   /* een voor een na de vaste bronnen, elk met een eigen uitkomst */
    size_t extra_aantal;
    int meld;             /* 1: per extra databank een rij (naam, uitkomst) in de tabel BRON van de uitvoer */
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
    "CREATE TEMP TABLE volnummers AS SELECT DISTINCT " INTL("ZADDRESS") " AS n FROM main.ZCALLRECORD "
    "  WHERE length(ZADDRESS) >= 6;"
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
    "CREATE TEMP TABLE volnummers AS SELECT DISTINCT " INTL("adres") " AS n FROM main.DEELNEMER "
    "  WHERE length(adres) >= 6 AND instr(adres, '@') = 0;"
    "CREATE TABLE META AS SELECT 'nieuwste' AS sleutel, (SELECT MAX(" SMS_TIJD ") FROM berichten.message m "
    "  WHERE COALESCE(m.item_type, 0) = 0) AS waarde;";

/* TEL-9: het adresboek van Contacts op de Mac (dat van de iPhone, via iCloud): alleen naam en nummer, alleen bij een
   nummer van het venster (temp.volnummers, het volle nummer) dat WhatsApp nog niet bij naam kent. Dezelfde tabel en
   kolommen als de contacten van WhatsApp; Z_PK ligt boven die van WhatsApp (:pk), zodat mac_gesprekken.Adresboek eerst
   WhatsApp en dan het oudste contact neemt. Een naam is voornaam en familienaam, anders de firma van de kaart. */
#define CNORM(x) NORM("replace(replace(" x ", '/', ''), char(160), '')")
static const char ADRESBOEK_VRAAG[] =
    "INSERT INTO main.ZWAADDRESSBOOKCONTACT (Z_PK, ZFULLNAME, ZWHATSAPPID, ZLID, ZPHONENUMBER) "
    "SELECT :pk + pk, naam, NULL, NULL, nummer FROM (SELECT r.Z_PK AS pk, p.ZFULLNUMBER AS nummer, "
    "  COALESCE(NULLIF(trim(COALESCE(r.ZFIRSTNAME, '') || ' ' || COALESCE(r.ZLASTNAME, '')), ''), "
    "  NULLIF(trim(r.ZORGANIZATION), '')) AS naam "
    "  FROM extra.ZABCDPHONENUMBER p JOIN extra.ZABCDRECORD r ON r.Z_PK = p.ZOWNER) "
    "WHERE naam IS NOT NULL AND " INTL("nummer") " IN (SELECT n FROM temp.volnummers) "
    "  AND " CNORM("nummer") " NOT IN (SELECT " NORM("ZPHONENUMBER") " FROM main.ZWAADDRESSBOOKCONTACT "
    "  WHERE ZPHONENUMBER IS NOT NULL) ORDER BY pk";

/* YT-1 en WEB-1: de geschiedenis van de browsers. Van elk bezoek alleen het tijdstip (Unix-seconden) en de naam van de
   site (site(), zoals browser_wacht.site: nooit het adres, het pad of een zoekopdracht); alleen bij een YouTube-video
   (video(), zoals youtube_wacht.video) ook de video-ID, de titel en hoe lang het tabblad openstond (alleen Chrome en
   Edge houden dat bij). Een andere titel verlaat de bron niet. */
static const char BROWSER_VRAGEN[] =
    "CREATE TABLE BEZOEK (browser TEXT, tijd REAL, site TEXT, video TEXT, titel TEXT, duur REAL);"
    "CREATE TABLE BRON (browser TEXT, uitkomst TEXT);"
    "CREATE TABLE META (sleutel TEXT, waarde);";
#define BEZOEK_IN "INSERT INTO main.BEZOEK (browser, tijd, site, video, titel, duur) SELECT :browser, t, site(a), " \
    "video(a), CASE WHEN video(a) IS NOT NULL THEN substr(k, 1, 200) END, CASE WHEN video(a) IS NOT NULL THEN d END FROM "
static const char CHROMIUM_VRAAG[] = BEZOEK_IN
    "(SELECT v.visit_time / 1000000.0 - 11644473600 AS t, u.url AS a, u.title AS k, v.visit_duration / 1000000.0 AS d "
    "  FROM extra.visits v JOIN extra.urls u ON u.id = v.url WHERE v.visit_time >= (:begin + 11644473600) * 1000000.0) "
    "WHERE site(a) IS NOT NULL";
static const char FIREFOX_VRAAG[] = BEZOEK_IN
    "(SELECT v.visit_date / 1000000.0 AS t, p.url AS a, p.title AS k, NULL AS d FROM extra.moz_historyvisits v "
    "  JOIN extra.moz_places p ON p.id = v.place_id WHERE v.visit_date >= :begin * 1000000.0) "
    "WHERE site(a) IS NOT NULL";
static const char SAFARI_VRAAG[] = BEZOEK_IN
    "(SELECT v.visit_time + 978307200 AS t, i.url AS a, v.title AS k, NULL AS d FROM extra.history_visits v "
    "  JOIN extra.history_items i ON i.id = v.history_item WHERE v.visit_time >= :begin - 978307200) "
    "WHERE site(a) IS NOT NULL";

static const Extra ADRESBOEK[] = {
    {"adresboek", "Library/Application Support/AddressBook", "AddressBook-v22.abcddb", 0, 0, ADRESBOEK_VRAAG},
    {"adresboek", "Library/Application Support/AddressBook/Sources", "AddressBook-v22.abcddb", 1, 0, ADRESBOEK_VRAAG},
};
static const Extra BROWSERS[] = {
    {"Chrome", "Library/Application Support/Google/Chrome", "History", 1, 1, CHROMIUM_VRAAG},
    {"Edge", "Library/Application Support/Microsoft Edge", "History", 1, 1, CHROMIUM_VRAAG},
    {"Firefox", "Library/Application Support/Firefox/Profiles", "places.sqlite", 1, 1, FIREFOX_VRAAG},
    {"Safari", "Library/Safari", "History.db", 0, 1, SAFARI_VRAAG},
};

static const Set SETS[] = {
    {"whatsapp", WHATSAPP, sizeof WHATSAPP / sizeof *WHATSAPP, WHATSAPP_VRAGEN, NULL, 0, 0},
    {"telefoon", TELEFOON, sizeof TELEFOON / sizeof *TELEFOON, TELEFOON_VRAGEN, ADRESBOEK,
     sizeof ADRESBOEK / sizeof *ADRESBOEK, 0},
    {"sms", SMS, sizeof SMS / sizeof *SMS, SMS_VRAGEN, ADRESBOEK, sizeof ADRESBOEK / sizeof *ADRESBOEK, 0},
    {"browser", NULL, 0, BROWSER_VRAGEN, BROWSERS, sizeof BROWSERS / sizeof *BROWSERS, 1},
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
   lezend kan SQLite de -shm niet aanmaken. Een eigen kopie met -wal opent schrijvend (EIGEN_KOPIE): alleen zo kan
   SQLite de WAL van de kopie inlezen. */
#define LEZEN "?mode=ro"
#define LEZEN_VAST "?mode=ro&immutable=1"
#define EIGEN_KOPIE "?mode=rw"
static int als_uri(const char *pad, const char *achter, char *uit, size_t ruimte) {
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
    return snprintf(uit + n, ruimte - n, "%s", achter) < (int)(ruimte - n);
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
    if (strncmp(naam, ".bron.sqlite", 12) == 0 && (naam[12] == 0 || strcmp(naam + 12, "-wal") == 0 ||
                                                   strcmp(naam + 12, "-shm") == 0 || strcmp(naam + 12, "-journal") == 0))
        return 1;   /* de eigen kopie van een browserdatabank (extra_een), als een ronde ze liet liggen */
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

/* ------------------------------------------------------------------ extra bronnen (T-0120 VOL-11, 01-11-2026) --- */

/* Een pad onder de thuismap openen, map per map zonder een symlink te volgen; het laatste deel als map (map != 0) of als
   gewoon bestand (zonder te blijven hangen op iets anders). Geeft een open descriptor, of -1 met errno (een weigering
   van macOS is EPERM, een symlink ELOOP). */
static int open_onder(const char *home, const char *pad, int map) {
    char deel[PATH_MAX];
    if (snprintf(deel, sizeof deel, "%s", pad) >= (int)sizeof deel) {
        errno = ENAMETOOLONG;
        return -1;
    }
    int fd = open(home, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    char *rest = deel, *stuk;
    while (fd >= 0 && (stuk = strsep(&rest, "/")) != NULL) {
        if (!*stuk) continue;
        int bestand = rest == NULL && !map;
        int volgend = openat(fd, stuk, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | (bestand ? O_NONBLOCK : O_DIRECTORY));
        int e = errno;
        close(fd);
        errno = e;
        fd = volgend;
    }
    struct stat st;
    if (fd >= 0 && (fstat(fd, &st) != 0 || (map ? !S_ISDIR(st.st_mode) : !S_ISREG(st.st_mode)))) {
        close(fd);
        errno = EINVAL;
        return -1;
    }
    return fd;
}

/* site(adres) en video(adres), alleen voor de vragen van de set browser. host_van: de host van een http- of https-adres
   in kleine letters, zonder gebruiker en poort, zoals urllib.parse.urlsplit(adres).hostname. Alleen letters, cijfers,
   punt, streep en liggend streepje (bij een IPv6-adres ook de dubbelpunt), hoogstens 253 tekens: wat er anders uitziet,
   verlaat de bron niet. */
static int host_van(const char *adres, char *uit, size_t ruimte) {
    const char *p = adres;
    if (strncasecmp(p, "http://", 7) == 0) p += 7;
    else if (strncasecmp(p, "https://", 8) == 0) p += 8;
    else return 0;
    size_t lang = strcspn(p, "/?#");
    for (size_t i = lang; i > 0; i--)
        if (p[i - 1] == '@') {
            p += i;
            lang -= i;
            break;
        }
    int v6 = lang > 0 && p[0] == '[';
    size_t n = 0;
    if (v6) {
        const char *eind = memchr(p, ']', lang);
        if (eind == NULL) return 0;
        p++;
        n = (size_t)(eind - p);
    } else {
        while (n < lang && p[n] != ':') n++;
    }
    if (n == 0 || n > 253 || n >= ruimte) return 0;
    for (size_t i = 0; i < n; i++) {
        char c = (char)tolower((unsigned char)p[i]);
        int goed = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '.' || c == '-' || c == '_' ||
                   (v6 && c == ':');
        if (!goed) return 0;
        uit[i] = c;
    }
    uit[n] = 0;
    return 1;
}

/* De naam van de site: de host zonder www. (browser_wacht.site). */
static void sql_site(sqlite3_context *ctx, int argc, sqlite3_value **argv) {
    (void)argc;
    const char *adres = (const char *)sqlite3_value_text(argv[0]);
    char host[256];
    if (adres == NULL || !host_van(adres, host, sizeof host)) {
        sqlite3_result_null(ctx);
        return;
    }
    const char *naam = strncmp(host, "www.", 4) == 0 ? host + 4 : host;
    if (*naam) sqlite3_result_text(ctx, naam, -1, SQLITE_TRANSIENT);
    else sqlite3_result_null(ctx);
}

/* %XX en + zoals urllib.parse.unquote_plus (een ongeldige % blijft staan), in uit (met afsluitende 0). Geeft de
   lengte, of 0 als het niet past. */
static int hexwaarde(char c) {
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
}

static size_t ontcijfer(const char *p, size_t n, char *uit, size_t ruimte) {
    size_t m = 0;
    for (size_t i = 0; i < n; i++) {
        if (m + 1 >= ruimte) return 0;
        if (p[i] == '%' && i + 2 < n && hexwaarde(p[i + 1]) >= 0 && hexwaarde(p[i + 2]) >= 0) {
            uit[m++] = (char)(hexwaarde(p[i + 1]) * 16 + hexwaarde(p[i + 2]));
            i += 2;
        } else {
            uit[m++] = p[i] == '+' ? ' ' : p[i];
        }
    }
    uit[m] = 0;
    return m;
}

static int is_video_id(const char *p, size_t n) {
    if (n < 6 || n > 20) return 0;
    for (size_t i = 0; i < n; i++)
        if (!((p[i] >= 'A' && p[i] <= 'Z') || (p[i] >= 'a' && p[i] <= 'z') || (p[i] >= '0' && p[i] <= '9') ||
              p[i] == '_' || p[i] == '-'))
            return 0;
    return 1;
}

/* De video-ID van een YouTube-adres (watch?v=, youtu.be/, shorts/, live/), anders NULL (youtube_wacht.video): zoeken,
   kanalen, de startpagina en reacties tellen niet. */
static void sql_video(sqlite3_context *ctx, int argc, sqlite3_value **argv) {
    (void)argc;
    const char *adres = (const char *)sqlite3_value_text(argv[0]);
    char host[256];
    if (adres == NULL || !host_van(adres, host, sizeof host)) {
        sqlite3_result_null(ctx);
        return;
    }
    const char *h = strncmp(host, "www.", 4) == 0 ? host + 4 : strncmp(host, "m.", 2) == 0 ? host + 2 : host;
    const char *pad = adres + (strncasecmp(adres, "https://", 8) == 0 ? 8 : 7);
    pad += strcspn(pad, "/?#");
    size_t padlang = strcspn(pad, "?#");
    const char *id = NULL;
    char waarde[32];
    size_t n = 0;
    if (strcmp(h, "youtu.be") == 0) {
        const char *q = pad;
        while (q < pad + padlang && *q == '/') q++;
        id = q;
        while (id + n < pad + padlang && id[n] != '/') n++;
    } else if (strcmp(h, "youtube.com") == 0 || strcmp(h, "music.youtube.com") == 0) {
        if (padlang == 6 && strncmp(pad, "/watch", 6) == 0 && pad[6] == '?') {
            /* de eerste niet-lege v, met sleutel en waarde ontcijferd zoals urllib.parse.parse_qs (Codex 01-11) */
            const char *q = pad + 7, *eind = q + strcspn(q, "#");
            while (q < eind && id == NULL) {
                size_t stuk = strcspn(q, "&#"), is = 0;
                while (is < stuk && q[is] != '=') is++;
                char sleutel[8];
                if (is < stuk && is + 1 < stuk && ontcijfer(q, is, sleutel, sizeof sleutel) == 1 && sleutel[0] == 'v') {
                    n = ontcijfer(q + is + 1, stuk - is - 1, waarde, sizeof waarde);
                    id = waarde;   /* te lang om te passen (n 0): geen video, zoals de Python-regel */
                }
                q += stuk + (q[stuk] == '&');
                if (stuk == 0 && *q != '&') break;
            }
        } else if (padlang > 8 && strncmp(pad, "/shorts/", 8) == 0) {
            id = pad + 8;
            n = strcspn(id, "/?#");
        } else if (padlang > 6 && strncmp(pad, "/live/", 6) == 0) {
            id = pad + 6;
            n = strcspn(id, "/?#");
        }
    }
    if (id != NULL && is_video_id(id, n)) sqlite3_result_text(ctx, id, (int)n, SQLITE_TRANSIENT);
    else sqlite3_result_null(ctx);
}

/* Een submap met een gewone naam: een profiel van een browser of een bron van het adresboek (geen punt vooraan, geen
   symlink, hoogstens 64 tekens uit letters, cijfers, spatie, punt, streep en liggend streepje). */
static int gewone_naam(const char *naam) {
    size_t n = strlen(naam);
    if (n == 0 || n > 64 || naam[0] == '.') return 0;
    for (size_t i = 0; i < n; i++)
        if (!((naam[i] >= 'A' && naam[i] <= 'Z') || (naam[i] >= 'a' && naam[i] <= 'z') ||
              (naam[i] >= '0' && naam[i] <= '9') || strchr(" ._-", naam[i]) != NULL))
            return 0;
    return 1;
}

static int pad_cmp(const void *a, const void *b) { return strcmp((const char *)a, (const char *)b); }

/* De databanken van een extra bron, als paden onder de thuismap, gesorteerd (een vaste volgorde, dus een vaste :pk).
   Geeft hun aantal (hoogstens MAX_PROFIELEN); 0 als de map er niet is; -1 met errno als ze er wel is maar macOS haar
   weigert. Of het bestand in een profiel echt bestaat, zegt pas extra_een. */
#define MAX_PROFIELEN 24
static int extra_paden(const char *home, const Extra *x, char paden[][PATH_MAX]) {
    if (!x->profielen) {
        if (snprintf(paden[0], PATH_MAX, "%s/%s", x->map, x->bestand) >= PATH_MAX) return 0;
        return 1;
    }
    int fd = open_onder(home, x->map, 1);
    if (fd < 0) return errno == ENOENT || errno == ENOTDIR ? 0 : -1;
    DIR *d = fdopendir(fd);
    if (d == NULL) {
        close(fd);
        return -1;
    }
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL && n < MAX_PROFIELEN) {
        struct stat st;
        if (!gewone_naam(e->d_name) || fstatat(dirfd(d), e->d_name, &st, AT_SYMLINK_NOFOLLOW) != 0 ||
            !S_ISDIR(st.st_mode))
            continue;
        if (snprintf(paden[n], PATH_MAX, "%s/%s/%s", x->map, e->d_name, x->bestand) < PATH_MAX) n++;
    }
    closedir(d);
    qsort(paden, (size_t)n, PATH_MAX, pad_cmp);
    return n;
}

/* Kopieer het open bestand bron (gecontroleerd: geen symlink, gewoon bestand) als naam in dirfd: nieuw (O_EXCL,
   O_NOFOLLOW, 0600). Geeft 1 als alles er staat. */
static int kopieer(int bron, int dirfd, const char *naam) {
    unlinkat(dirfd, naam, 0);
    int fd = openat(dirfd, naam, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return 0;
    static unsigned char buf[1 << 20];
    int goed = 1;
    for (;;) {
        ssize_t r = read(bron, buf, sizeof buf);
        if (r < 0 && errno == EINTR) continue;
        if (r < 0) goed = 0;
        if (r <= 0) break;
        for (ssize_t gedaan = 0; goed && gedaan < r;) {
            ssize_t w = write(fd, buf + gedaan, (size_t)(r - gedaan));
            if (w < 0 && errno == EINTR) continue;
            if (w <= 0) goed = 0;
            else gedaan += w;
        }
        if (!goed) break;
    }
    goed = close(fd) == 0 && goed;
    if (!goed) unlinkat(dirfd, naam, 0);
    return goed;
}

static void kopie_weg(int dirfd) {
    const char *namen[] = {".bron.sqlite", ".bron.sqlite-wal", ".bron.sqlite-shm", ".bron.sqlite-journal"};
    for (size_t i = 0; i < sizeof namen / sizeof *namen; i++) unlinkat(dirfd, namen[i], 0);
}

/* Een databank van een extra bron lezen: openen langs het pad zonder symlink, bij x->kopie eerst een eigen kopie (met
   haar -wal) in de privemap van de set (privemap: het volle pad van dirfd), dan de vraag van de bron met :begin, :pk en
   :browser. De kopie is weg voor de functie terugkeert. Geeft de uitkomst: ok, ontbreekt, geweigerd, onverwacht of fout. */
static const char *extra_een(sqlite3 *db, const char *home, int dirfd, const char *privemap, const Extra *x,
                             const char *pad, double begin, sqlite3_int64 pk) {
    char vol[PATH_MAX], wal[PATH_MAX + 8], uri[3 * PATH_MAX];
    struct stat id, st;
    int bron = open_onder(home, pad, 0);
    if (bron < 0) return uit_errno(errno);
    if (fstat(bron, &id) != 0) {
        close(bron);
        return "fout";
    }
    int met_wal = 0, goed = 1;
    if (x->kopie) {
        kopie_weg(dirfd);
        goed = kopieer(bron, dirfd, ".bron.sqlite");
        snprintf(wal, sizeof wal, "%s-wal", pad);
        int w = goed ? open_onder(home, wal, 0) : -1;
        if (w >= 0) {
            met_wal = 1;
            goed = kopieer(w, dirfd, ".bron.sqlite-wal");
            close(w);
        } else if (goed && errno != ENOENT) {
            goed = 0;
        }
        goed = goed && snprintf(vol, sizeof vol, "%s/.bron.sqlite", privemap) < (int)sizeof vol &&
               als_uri(vol, met_wal ? EIGEN_KOPIE : LEZEN_VAST, uri, sizeof uri);
    } else {
        goed = snprintf(vol, sizeof vol, "%s/%s", home, pad) < (int)sizeof vol &&
               snprintf(wal, sizeof wal, "%s-wal", vol) < (int)sizeof wal &&
               als_uri(vol, lstat(wal, &st) != 0 && errno == ENOENT ? LEZEN_VAST : LEZEN, uri, sizeof uri);
    }
    close(bron);
    const char *uitkomst = goed ? "ok" : "fout";
    sqlite3_stmt *stmt = NULL;
    int rc = goed ? sqlite3_prepare_v2(db, "ATTACH ?1 AS extra", -1, &stmt, NULL) : SQLITE_ERROR;
    if (goed) {
        if (rc == SQLITE_OK) rc = sqlite3_bind_text(stmt, 1, uri, -1, SQLITE_TRANSIENT);
        if (rc == SQLITE_OK) rc = sqlite3_step(stmt) == SQLITE_DONE ? SQLITE_OK : sqlite3_errcode(db);
        sqlite3_finalize(stmt);
        if (rc != SQLITE_OK) {
            uitkomst = rc == SQLITE_AUTH || rc == SQLITE_PERM ? "geweigerd" : "fout";
        } else {
            if (!x->kopie && !zelfde_bestand(db, "extra", &id)) {
                uitkomst = "onverwacht";   /* het pad wees intussen naar een ander bestand */
            } else {
                /* Een vraag die faalt, wijst op een ander schema: onverwacht, en van deze bron komt dan niets mee. */
                stmt = NULL;
                rc = sqlite3_prepare_v2(db, x->vraag, -1, &stmt, NULL);
                if (rc == SQLITE_OK) {
                    int i;
                    if ((i = sqlite3_bind_parameter_index(stmt, ":begin")) > 0)
                        sqlite3_bind_double(stmt, i, begin + APPLE_EPOCH);
                    if ((i = sqlite3_bind_parameter_index(stmt, ":pk")) > 0) sqlite3_bind_int64(stmt, i, pk);
                    if ((i = sqlite3_bind_parameter_index(stmt, ":browser")) > 0)
                        sqlite3_bind_text(stmt, i, x->naam, -1, SQLITE_STATIC);
                    sqlite3_exec(db, "SAVEPOINT extra", NULL, NULL, NULL);
                    rc = sqlite3_step(stmt) == SQLITE_DONE ? SQLITE_OK : sqlite3_errcode(db);
                    sqlite3_finalize(stmt);
                    sqlite3_exec(db, rc == SQLITE_OK ? "RELEASE extra" : "ROLLBACK TO extra; RELEASE extra", NULL,
                                 NULL, NULL);
                } else {
                    sqlite3_finalize(stmt);
                }
                if (rc != SQLITE_OK)
                    uitkomst = rc == SQLITE_AUTH || rc == SQLITE_PERM ? "geweigerd" : rc == SQLITE_ERROR ? "onverwacht"
                                                                                                        : "fout";
            }
            sqlite3_exec(db, "DETACH extra", NULL, NULL, NULL);
        }
    }
    if (x->kopie) kopie_weg(dirfd);
    return uitkomst;
}

/* Alle extra bronnen van een set; per naam de uitkomst (ok als elke databank ok was, anders de eerste andere;
   ontbreekt als er geen databank was) in namen en uitkomsten, en bij set->meld een rij per databank in BRON. Geeft het
   aantal namen; *ok het aantal databanken met uitkomst ok, *geweigerd dat met geweigerd. */
#define MAX_EXTRA 8
static void noteer(sqlite3 *db, const Set *set, const char *naam, const char *u, const char **uitkomst, int *ok,
                   int *geweigerd) {
    *ok += strcmp(u, "ok") == 0;
    *geweigerd += strcmp(u, "geweigerd") == 0;
    if (uitkomst != NULL && (strcmp(*uitkomst, "ontbreekt") == 0 || (strcmp(*uitkomst, "ok") == 0 && strcmp(u, "ok") != 0)))
        *uitkomst = u;
    if (!set->meld) return;
    sqlite3_stmt *stmt = NULL;
    if (sqlite3_prepare_v2(db, "INSERT INTO main.BRON VALUES (?1, ?2)", -1, &stmt, NULL) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, naam, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, u, -1, SQLITE_STATIC);
        sqlite3_step(stmt);
    }
    sqlite3_finalize(stmt);
}

/* Codex 01-11: een extra bron mag de set niet ophouden. De runner wacht hoogstens 120 seconden op de hele kopie: per
   databank hoogstens EXTRA_WACHT_MS op een slot, en na EXTRA_BUDGET seconden geen nieuwe extra databank meer (fout). */
#define EXTRA_WACHT_MS 2000
#define EXTRA_BUDGET 45
static size_t extra_lezen(sqlite3 *db, const char *home, int dirfd, const char *privemap, const Set *set, double begin,
                          const char *namen[MAX_EXTRA], const char *uitkomsten[MAX_EXTRA], int *ok, int *geweigerd) {
    static char paden[MAX_PROFIELEN][PATH_MAX];
    size_t n = 0;
    sqlite3_int64 k = 0;
    time_t start = time(NULL);
    *ok = *geweigerd = 0;
    sqlite3_busy_timeout(db, EXTRA_WACHT_MS);
    for (size_t i = 0; i < set->extra_aantal; i++) {
        const Extra *x = &set->extra[i];
        size_t j = 0;
        while (j < n && strcmp(namen[j], x->naam) != 0) j++;
        if (j == n && n < MAX_EXTRA) {
            namen[n] = x->naam;
            uitkomsten[n++] = "ontbreekt";
        }
        const char **uitkomst = j < n ? &uitkomsten[j] : NULL;
        int aantal = extra_paden(home, x, paden);
        if (aantal < 0) noteer(db, set, x->naam, uit_errno(errno), uitkomst, ok, geweigerd);
        for (int p = 0; p < aantal; p++) {
            const char *u = time(NULL) - start > EXTRA_BUDGET ? "fout" :
                            extra_een(db, home, dirfd, privemap, x, paden[p], begin, ++k * 1000000000LL);
            if (strcmp(u, "ontbreekt") != 0)   /* een profiel zonder databank telt niet */
                noteer(db, set, x->naam, u, uitkomst, ok, geweigerd);
        }
    }
    return n;
}

int main(int argc, char *argv[]) {
    const Set *set = NULL;
    for (size_t i = 0; argc == 2 && i < sizeof SETS / sizeof *SETS; i++)
        if (strcmp(argv[1], SETS[i].naam) == 0) set = &SETS[i];
    if (set == NULL) {
        fprintf(stderr, "Gebruik: MacGesprekkenKopie whatsapp|telefoon|sms|browser\n");
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

    const char *uitkomst[8] = {0}, *extra_naam[MAX_EXTRA] = {0}, *extra_uitkomst[MAX_EXTRA] = {0};
    size_t extra_n = 0;
    const char *geheel = "ok";
    sqlite3 *db = NULL;
    if (sqlite3_open_v2(":memory:", &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_URI |
                        SQLITE_OPEN_NOFOLLOW, NULL) != SQLITE_OK) geheel = "fout";
    if (db) sqlite3_busy_timeout(db, 15000);
    if (db && (sqlite3_create_function_v2(db, "site", 1, SQLITE_UTF8 | SQLITE_DETERMINISTIC, NULL, sql_site, NULL, NULL,
                                          NULL) != SQLITE_OK ||
               sqlite3_create_function_v2(db, "video", 1, SQLITE_UTF8 | SQLITE_DETERMINISTIC, NULL, sql_video, NULL,
                                          NULL, NULL) != SQLITE_OK))
        geheel = "fout";
    for (size_t i = 0; i < set->aantal; i++) {
        char pad[PATH_MAX], wal[PATH_MAX + 8], uri[3 * PATH_MAX], sql[256];
        struct stat st, id;
        uitkomst[i] = "ok";
        if (snprintf(pad, sizeof pad, "%s/%s", home, set->bronnen[i].pad) >= (int)sizeof pad ||
            snprintf(wal, sizeof wal, "%s-wal", pad) >= (int)sizeof wal ||
            !als_uri(pad, lstat(wal, &st) != 0 && errno == ENOENT ? LEZEN_VAST : LEZEN, uri, sizeof uri)) {
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
        char vragen[sizeof WHATSAPP_VRAGEN + sizeof TELEFOON_VRAGEN + sizeof SMS_VRAGEN + sizeof BROWSER_VRAGEN + 64];
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
            /* VOL-11: de extra bronnen, een voor een (temp.nummers bestaat nog); geen enkele gelezen en wel een
               weigering, bij een set zonder vaste bronnen: dan heeft de helper geen toegang */
            char privemap[PATH_MAX];
            int ok = 0, geweigerd = 0;
            if (set->extra_aantal > 0 && snprintf(privemap, sizeof privemap, "%s/Library/Caches/mijnagents/mac-gesprekken/%s",
                                                  home, set->naam) < (int)sizeof privemap)
                extra_n = extra_lezen(db, home, fd, privemap, set, begin, extra_naam, extra_uitkomst, &ok, &geweigerd);
            if (set->aantal == 0 && ok == 0 && geweigerd > 0) geheel = "geweigerd";
            sqlite3_exec(db, "DROP TABLE IF EXISTS temp.adressen; DROP TABLE IF EXISTS temp.nummers; "
                             "DROP TABLE IF EXISTS temp.volnummers; DROP TABLE IF EXISTS temp.toegelaten", NULL, NULL,
                         NULL);
            buf = strcmp(geheel, "ok") == 0 ? sqlite3_serialize(db, "main", &n, 0) : NULL;
            if (strcmp(geheel, "ok") == 0 && (buf == NULL || n < 100 || !schrijf(fd, uitnaam, buf, (size_t)n)))
                geheel = "fout";
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
    if (set->extra_aantal > 0 && lengte < (int)sizeof status)
        lengte += snprintf(status + lengte, sizeof status - (size_t)lengte, "}, \"extra\": {");
    for (size_t i = 0; i < extra_n && lengte < (int)sizeof status; i++)
        lengte += snprintf(status + lengte, sizeof status - (size_t)lengte, "%s\"%s\": \"%s\"", i ? ", " : "",
                           extra_naam[i], extra_uitkomst[i]);
    if (lengte < (int)sizeof status)
        lengte += snprintf(status + lengte, sizeof status - (size_t)lengte, "}}\n");
    int bewaard = lengte < (int)sizeof status && schrijf(fd, "status.json", (const unsigned char *)status, (size_t)lengte);
    close(fd);
    fputs(status, stdout);
    if (!bewaard) return EX_IOERR;
    return strcmp(geheel, "ok") == 0 ? 0 : strcmp(geheel, "geweigerd") == 0 ? 2 : 1;
}
