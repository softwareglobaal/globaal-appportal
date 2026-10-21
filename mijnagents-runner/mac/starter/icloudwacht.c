/* Vaste macOS-starter: alleen dit programma krijgt Full Disk Access. */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pwd.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sysexits.h>
#include <unistd.h>

#define SCRIPT "/Library/Application Support/iCloudWacht/icloud_wacht.py"
#define PYTHON "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9"

/* Geen heropening op naam: Python leest precies de gecontroleerde inode. */
static const char python_start[] =
    "import os,sys; p='" SCRIPT "'; sys.argv[0]=p; "
    "bron=os.fdopen(%d,'rb').read(); "
    "exec(compile(bron,p,'exec'),{'__name__':'__main__','__file__':p})";

static int veilig_pad(const char *pad, int map) {
    struct stat st;
    return lstat(pad, &st) == 0 && st.st_uid == 0 &&
           (st.st_mode & (S_IWGRP | S_IWOTH)) == 0 &&
           (map ? S_ISDIR(st.st_mode) : S_ISREG(st.st_mode));
}

int main(int argc, char *argv[]) {
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--taken") != 0)) {
        fprintf(stderr, "Gebruik: iCloudWacht [--taken]\n");
        return EX_USAGE;
    }
    if (!veilig_pad("/", 1) || !veilig_pad("/Library", 1) ||
        !veilig_pad("/Library/Application Support", 1) ||
        !veilig_pad("/Library/Application Support/iCloudWacht", 1) ||
        !veilig_pad(SCRIPT, 0)) {
        fprintf(stderr, "iCloudWacht: onveilig root-pad of script\n");
        return EX_CONFIG;
    }
    /* /usr/bin/python3 is een xcrun-shim met een gebruikerscache. Gebruik de
       echte, root-eigen interpreter en verifieer ook al zijn voorouders. */
    if (!veilig_pad("/Library/Developer", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library/Frameworks", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9", 1) ||
        !veilig_pad("/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin", 1) ||
        !veilig_pad(PYTHON, 0)) {
        fprintf(stderr, "iCloudWacht: veilige Python 3.9 ontbreekt of heeft onveilige rechten\n");
        return EX_CONFIG;
    }

    int fd = open(SCRIPT, O_RDONLY | O_NOFOLLOW);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) ||
        st.st_uid != 0 || (st.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
        if (fd >= 0) close(fd);
        fprintf(stderr, "iCloudWacht: script kon niet veilig worden geopend\n");
        return EX_CONFIG;
    }
    int kind_fd = fcntl(fd, F_DUPFD, 3);
    close(fd);
    if (kind_fd < 0) {
        fprintf(stderr, "iCloudWacht: scriptdescriptor kon niet worden doorgegeven\n");
        return EX_CONFIG;
    }
    fd = kind_fd;

    struct passwd *gebruiker = getpwuid(getuid());
    if (gebruiker == NULL || gebruiker->pw_dir == NULL) {
        close(fd);
        fprintf(stderr, "iCloudWacht: Mac-gebruiker onbekend\n");
        return EX_CONFIG;
    }
    char home[PATH_MAX + sizeof("HOME=")];
    char start[sizeof(python_start) + 16];
    if (snprintf(home, sizeof home, "HOME=%s", gebruiker->pw_dir) >= (int)sizeof home ||
        snprintf(start, sizeof start, python_start, fd) >= (int)sizeof start) {
        close(fd);
        fprintf(stderr, "iCloudWacht: startgegevens te lang\n");
        return EX_CONFIG;
    }

    /* De vier optionele iCloud-variabelen hebben veilige defaults. Omgevingswaarden
       van andere gebruikersprocessen mogen de bron, bestemming of bord-URL niet sturen. */
    char *omgeving[] = {home, "PATH=/usr/bin:/bin", "LANG=en_US.UTF-8", NULL};
    char *args[] = {PYTHON, "-I", "-B", "-c", start,
                    argc == 2 ? "--taken" : NULL, NULL};
    pid_t kind;
    int fout = posix_spawn(&kind, args[0], NULL, NULL, args, omgeving);
    close(fd);
    if (fout != 0) {
        fprintf(stderr, "iCloudWacht: Python kon niet starten\n");
        return EX_CONFIG;
    }

    int status;
    while (waitpid(kind, &status, 0) == -1) {
        if (errno != EINTR) {
            fprintf(stderr, "iCloudWacht: wachtronde kon niet worden gevolgd\n");
            return EX_CONFIG;
        }
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    fprintf(stderr, "iCloudWacht: onbekende eindstatus\n");
    return EX_CONFIG;
}
