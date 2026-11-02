/* BrowserWacht: het enige programma met Full Disk Access voor De Browserwacht (T-0077, overleg 2026-11-02-websitewacht
   P2 en P5). Naar het patroon van icloudwacht.c, met een verschil: het script staat niet root-eigen onder /Library (dat
   vraagt sudo bij elke uitrol), maar in de eigen map van de gebruiker. Daarom is de inhoud van het script vastgepind: de
   SHA-256 van browser_wacht.py zit in dit programma (SCRIPT_SHA256, bij de bouw meegegeven). De starter leest het
   script een keer in het geheugen, vergelijkt de hash en geeft precies die inhoud via een pijp aan Python. Een ander
   script, een gewijzigd script of een symlink start nooit. Verandert het script, dan is er een nieuwe starter met een
   nieuwe cdhash, en geeft Mehdi opnieuw Full Disk Access (System Settings > Privacy & Security > Full Disk Access).
   Geen omgeving, geen paden van buiten; alleen --proef gaat door: de wacht zegt dan alleen of het Chrome-profiel
   leesbaar is, zonder tellingen of sitenamen (Codex 02-11, punt 1: --droog zou elk proces van deze gebruiker de
   bezochte sites laten lezen). */
#include <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pwd.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sysexits.h>
#include <unistd.h>

#ifndef SCRIPT_SHA256
#error "SCRIPT_SHA256 (64 hextekens van browser_wacht.py) hoort bij de bouw meegegeven te worden"
#endif
#define SCRIPT_REL "Library/Application Support/mijnagents/browser-wacht/browser_wacht.py"
#define SCRIPT_MAX 60000   /* past in een pijp zonder te blokkeren (64 KiB) */
#define PYTHON "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9"

static const char python_start[] =
    "import os,sys; p='%s'; sys.argv[0]=p; "
    "bron=os.fdopen(%d,'rb').read(); "
    "exec(compile(bron,p,'exec'),{'__name__':'__main__','__file__':p})";

/* Een root-eigen pad dat niemand anders kan schrijven (zoals icloudwacht.c). */
static int veilig_pad(const char *pad, int map) {
    struct stat st;
    return lstat(pad, &st) == 0 && st.st_uid == 0 && (st.st_mode & (S_IWGRP | S_IWOTH)) == 0 &&
           (map ? S_ISDIR(st.st_mode) : S_ISREG(st.st_mode));
}

static int hex_gelijk(const unsigned char *d, const char *hex) {
    if (strlen(hex) != 2 * CC_SHA256_DIGEST_LENGTH) return 0;
    for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; i++) {
        char twee[3];
        snprintf(twee, sizeof twee, "%02x", d[i]);
        if (twee[0] != hex[2 * i] || twee[1] != hex[2 * i + 1]) return 0;
    }
    return 1;
}

int main(int argc, char *argv[]) {
    int proef = argc == 2 && strcmp(argv[1], "--proef") == 0;
    if (argc > 2 || (argc == 2 && !proef)) {
        fprintf(stderr, "Gebruik: BrowserWacht [--proef]\n");
        return EX_USAGE;
    }
    static const char *python_mappen[] = {
        "/", "/Library", "/Library/Developer", "/Library/Developer/CommandLineTools",
        "/Library/Developer/CommandLineTools/Library", "/Library/Developer/CommandLineTools/Library/Frameworks",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9",
        "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin"};
    for (size_t i = 0; i < sizeof python_mappen / sizeof *python_mappen; i++)
        if (!veilig_pad(python_mappen[i], 1)) {
            fprintf(stderr, "BrowserWacht: onveilig root-pad %s\n", python_mappen[i]);
            return EX_CONFIG;
        }
    if (!veilig_pad(PYTHON, 0)) {
        fprintf(stderr, "BrowserWacht: veilige Python 3.9 ontbreekt of heeft onveilige rechten\n");
        return EX_CONFIG;
    }

    struct passwd *gebruiker = getpwuid(getuid());
    if (gebruiker == NULL || gebruiker->pw_dir == NULL || gebruiker->pw_dir[0] != '/') {
        fprintf(stderr, "BrowserWacht: Mac-gebruiker onbekend\n");
        return EX_CONFIG;
    }
    char script[PATH_MAX];
    if (snprintf(script, sizeof script, "%s/%s", gebruiker->pw_dir, SCRIPT_REL) >= (int)sizeof script) {
        fprintf(stderr, "BrowserWacht: scriptpad te lang\n");
        return EX_CONFIG;
    }
    /* Het script: een gewoon bestand van deze gebruiker, geen symlink, alleen door hem schrijfbaar. */
    int fd = open(script, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
        (st.st_mode & (S_IWGRP | S_IWOTH)) != 0 || st.st_size <= 0 || st.st_size > SCRIPT_MAX) {
        if (fd >= 0) close(fd);
        fprintf(stderr, "BrowserWacht: script ontbreekt, is niet van de gebruiker of is te groot\n");
        return EX_CONFIG;
    }
    size_t n = (size_t)st.st_size, gelezen = 0;
    unsigned char *bron = malloc(n + 1);
    if (bron == NULL) {
        close(fd);
        return EX_OSERR;
    }
    while (gelezen < n) {
        ssize_t r = read(fd, bron + gelezen, n - gelezen);
        if (r < 0 && errno == EINTR) continue;
        if (r <= 0) break;
        gelezen += (size_t)r;
    }
    close(fd);
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(bron, (CC_LONG)gelezen, digest);
    if (gelezen != n || !hex_gelijk(digest, SCRIPT_SHA256)) {
        free(bron);
        fprintf(stderr, "BrowserWacht: het script is niet het script waarvoor deze starter gebouwd is; "
                        "nieuwe uitrol nodig (uitrol_browser_wacht.sh)\n");
        return EX_CONFIG;
    }

    /* Precies de gecontroleerde inhoud gaat naar Python, via een pijp: geen tweede lezing van de schijf. */
    int pijp[2];
    if (pipe(pijp) != 0) {
        free(bron);
        return EX_OSERR;
    }
    size_t geschreven = 0;
    while (geschreven < n) {
        ssize_t w = write(pijp[1], bron + geschreven, n - geschreven);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) break;
        geschreven += (size_t)w;
    }
    close(pijp[1]);
    free(bron);
    if (geschreven != n) {
        close(pijp[0]);
        fprintf(stderr, "BrowserWacht: script kon niet worden doorgegeven\n");
        return EX_OSERR;
    }
    int kind_fd = fcntl(pijp[0], F_DUPFD, 3);   /* zonder CLOEXEC: Python erft hem */
    close(pijp[0]);
    if (kind_fd < 0) return EX_OSERR;

    char home[PATH_MAX + sizeof("HOME=")];
    char start[sizeof(python_start) + PATH_MAX + 16];
    if (snprintf(home, sizeof home, "HOME=%s", gebruiker->pw_dir) >= (int)sizeof home ||
        snprintf(start, sizeof start, python_start, script, kind_fd) >= (int)sizeof start) {
        fprintf(stderr, "BrowserWacht: startgegevens te lang\n");
        return EX_CONFIG;
    }
    char *omgeving[] = {home, "PATH=/usr/bin:/bin", "LANG=en_US.UTF-8", NULL};
    char *args[] = {PYTHON, "-I", "-B", "-c", start, proef ? "--proef" : NULL, NULL};
    pid_t kind;
    if (posix_spawn(&kind, args[0], NULL, NULL, args, omgeving) != 0) {
        fprintf(stderr, "BrowserWacht: Python kon niet starten\n");
        return EX_CONFIG;
    }
    close(kind_fd);
    int status;
    while (waitpid(kind, &status, 0) == -1)
        if (errno != EINTR) return EX_CONFIG;
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return EX_CONFIG;
}
