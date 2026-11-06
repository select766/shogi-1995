.text
.global shogi_raw_syscall
.hidden shogi_raw_syscall
.type shogi_raw_syscall,@function
shogi_raw_syscall:
    push %ebx
    push %esi
    push %edi
    push %ebp
    mov 20(%esp),%eax
    mov 24(%esp),%ebx
    mov 28(%esp),%ecx
    mov 32(%esp),%edx
    mov 36(%esp),%esi
    mov 40(%esp),%edi
    mov 44(%esp),%ebp
    int $128
    pop %ebp
    pop %edi
    pop %esi
    pop %ebx
    ret
.section .note.GNU-stack,"",@progbits
