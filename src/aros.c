#include <wchar.h>
#include <wctype.h>
#include <stdarg.h>
#include <stdio.h>

int wcscasecmp(const wchar_t *a, const wchar_t *b)
{
    while (*a && towlower(*a) == towlower(*b)) { a++; b++; }
    return (int)towlower(*a) - (int)towlower(*b);
}

#ifdef HW_BUILD_FOR_DEBUGGING
void ssLog(const char *fmt, ...)
{
    FILE *f = fopen("sstream_debug.log", "a");
    va_list ap;

    if (f == NULL)
    {
        return;
    }
    fprintf(f, "[%u ms] ", (unsigned)SDL_GetTicks());
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}
#endif
