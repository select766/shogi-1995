/* Read-only YBB and rotated-key lookup for study-book-flips.py (little-endian host). */
#include <fcntl.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static const unsigned char *book, *flipped;
static uint64_t count;

int init(const char *path, const char *mirror)
{
    int f = open(path, O_RDONLY), g = open(mirror, O_RDONLY);
    struct stat book_stat, flip_stat;
    if (f < 0 || g < 0 || fstat(f, &book_stat) || fstat(g, &flip_stat))
        return -1;
    if (book_stat.st_size < 32 || flip_stat.st_size <= 0)
        return -1;
    book = mmap(NULL, book_stat.st_size, PROT_READ, MAP_PRIVATE, f, 0);
    flipped = mmap(NULL, flip_stat.st_size, PROT_READ, MAP_PRIVATE, g, 0);
    close(f);
    close(g);
    if (book == MAP_FAILED || flipped == MAP_FAILED)
        return -2;
    memcpy(&count, book + 16, 8);
    if (count > (uint64_t)(book_stat.st_size - 32) / 44 ||
        count != (uint64_t)flip_stat.st_size / 36 || flip_stat.st_size % 36)
        return -3;
    return 0;
}

uint64_t lookup(const unsigned char *key)
{
    uint64_t lo = 0, hi = count;
    while (lo < hi) {
        uint64_t mid = lo + (hi - lo) / 2;
        int cmp = memcmp(key, book + 32 + mid * 44, 32);
        if (cmp > 0) lo = mid + 1;
        else hi = mid;
    }
    if (lo < count && !memcmp(key, book + 32 + lo * 44, 32))
        return lo + 1;
    lo = 0;
    hi = count;
    while (lo < hi) {
        uint64_t mid = lo + (hi - lo) / 2;
        int cmp = memcmp(key, flipped + mid * 36, 32);
        if (cmp > 0) lo = mid + 1;
        else hi = mid;
    }
    if (lo < count && !memcmp(key, flipped + lo * 36, 32)) {
        uint32_t index;
        memcpy(&index, flipped + lo * 36 + 32, 4);
        return (UINT64_C(1) << 63) | ((uint64_t)index + 1);
    }
    return 0;
}
