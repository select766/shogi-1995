#ifndef RULES_H
#define RULES_H
#define MAX_PLY 2048
/* Positive pieces are sente; promoted pieces are base + 8. Gold/king never promote. */
typedef struct { int b[81], h[2][8], turn; } Position;
typedef struct { int from, to, promote, drop; } Move;
void initial(Position *p);
int in_check(const Position *p, int side);
int parse_move(const char *s, Move *m);
void move_text(Move m, char *s);
int legal(const Position *p, Move m);
void apply(Position *p, Move m);
int has_legal(const Position *p);
int declaration(const Position *p);
int read_sfen(Position *p, const char *s);
#endif
