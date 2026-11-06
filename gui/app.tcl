#!/usr/bin/wish -f
# Tcl 7.4 / Tk 4.0 compatible. Deliberately no Unicode, threads, or modern Tk APIs.
set home [file dirname [info script]]
if {[info exists env(SHOGI_GUI_HOME)]} {set home $env(SHOGI_GUI_HOME)}
set assets $home/assets
set core $home/core
if {[info exists env(SHOGI_GUI_CORE)]} {set core $env(SHOGI_GUI_CORE)}
set config $home/engine.conf
if {[info exists env(SHOGI_GUI_CONFIG)]} {set config $env(SHOGI_GUI_CONFIG)}
set logfile /tmp/shogi-gui.log
if {[info exists env(SHOGI_GUI_LOG)]} {set logfile $env(SHOGI_GUI_LOG)}
set command [list $core --config $config --log $logfile]
if {[info exists env(SHOGI_GUI_DEBUG)]} {lappend command --debug}
set channel [open "|$command" r+]
set turn 0
set active 0
set status settings
set ply 0
set board {}
set hands {}
set selected -1
set selectedDrop 0
set targets {}
set view settings
set player0 human
set player1 ai
set minutes 5
set increment 10
set records {}
set promotion {}
set lastBoard {}
set lastHands {}
set errorMessage {}
option add *Font fixed
option add *background #d9d9d9
option add *activeBackground #ececec
wm title . "Shogi 1995"
wm geometry . 748x552+20+20
wm minsize . 748 552
wm protocol . WM_DELETE_WINDOW shutdown

proc bm {name} {global assets; return @$assets/$name.xbm}
proc caption {widget name} {label $widget -bitmap [bm $name] -anchor w}
proc send {line} {
    global channel
    if {[catch {puts $channel $line; flush $channel} reason]} {connectionLost}
}
proc shutdown {} {
    global channel
    catch {puts $channel close; flush $channel}
    catch {close $channel}
    destroy .
}
proc tkerror {msg} {bgerror $msg}
proc bgerror {msg} {
    global errorInfo logfile
    set f [open $logfile a]; puts $f "TK ERROR: $msg\n$errorInfo"; close $f
    catch {.bottom.status configure -bitmap {} -text "GUI error: see $logfile"}
}
proc settings {} {
    global view active
    if {$active} {return}
    set view settings
    foreach w [winfo children .] {destroy $w}
    frame .s
    pack .s -fill both -expand 1 -padx 65 -pady 20
    caption .s.title settings
    pack .s.title -anchor w -pady 12
    foreach side {0 1} {
        set name [lindex {sente gote} $side]
        frame .s.p$side
        caption .s.p$side.label $name
        radiobutton .s.p$side.human -bitmap [bm human] -variable player$side -value human
        radiobutton .s.p$side.ai -bitmap [bm ai] -variable player$side -value ai
        pack .s.p$side.label -side left -padx 20
        pack .s.p$side.human .s.p$side.ai -side left -padx 20
        pack .s.p$side -anchor w -pady 12
    }
    foreach key {minutes increment} {
        if {$key == "minutes"} {set label time} else {set label increment}
        frame .s.$key
        caption .s.$key.label $label
        entry .s.$key.entry -textvariable $key -width 8 -relief sunken
        pack .s.$key.label -side left -padx 20
        pack .s.$key.entry -side right -padx 20
        pack .s.$key -fill x -pady 12
    }
    caption .s.help help
    pack .s.help -anchor w -padx 20 -pady 10
    label .s.error -text {} -foreground #a00000
    pack .s.error
    button .s.start -bitmap [bm start] -command startGame -padx 28 -pady 6
    pack .s.start -pady 12
    caption .s.credit credit
    pack .s.credit -anchor e
}
proc startGame {} {
    global player0 player1 minutes increment selected selectedDrop records targets promotion
    if {[catch {expr double($minutes)} m] || [catch {expr double($increment)} i]} {
        .s.error configure -text "Enter numeric minutes and increment."; return
    }
    if {!($m >= 0 && $m <= 1440 && $i >= 0 && $i <= 3600)} {
        .s.error configure -text "Minutes: 0..1440 / increment: 0..3600"; return
    }
    set selected -1; set selectedDrop 0; set targets {}; set records {}; set promotion {}
    gameScreen
    send "new $player0 $player1 [expr $m*60] $i"
}
proc gameScreen {} {
    global view lastBoard lastHands
    set view game
    foreach w [winfo children .] {destroy $w}
    frame .top
    pack .top -side top -fill x -padx 10 -pady 4
    foreach side {0 1} {
        set name [lindex {sente gote} $side]
        caption .top.l$side $name
        label .top.t$side -text 05:00 -width 10 -relief sunken -font 9x15
        pack .top.l$side .top.t$side -side left -padx 7
    }
    frame .body
    pack .body -side top -fill both -expand 1 -padx 8
    canvas .body.board -width 440 -height 464 -highlightthickness 0
    pack .body.board -side left -anchor n
    frame .body.record
    pack .body.record -side left -fill both -expand 1 -padx 5
    caption .body.record.title record
    pack .body.record.title -side top -anchor w
    scrollbar .body.record.scroll -command {.body.record.list yview}
    canvas .body.record.list -width 252 -height 380 -background white -yscrollcommand {.body.record.scroll set} -highlightthickness 1 -highlightbackground #888888
    pack .body.record.scroll -side right -fill y
    pack .body.record.list -side left -fill both -expand 1
    bind .body.record.list <Button-4> {.body.record.list yview scroll -3 units}
    bind .body.record.list <Button-5> {.body.record.list yview scroll 3 units}
    catch {bind .body.record.list <MouseWheel> {.body.record.list yview scroll [expr -%D/120] units}}
    frame .bottom
    pack .bottom -side bottom -fill x -padx 12 -pady 5
    label .bottom.status -bitmap [bm choose] -anchor w
    pack .bottom.status -side left
    button .bottom.action -bitmap [bm resign] -command {send action}
    button .bottom.next -bitmap [bm next] -command settings -state disabled
    pack .bottom.next .bottom.action -side right -padx 4
    bind .body.board <Button-1> {click %x %y}
    set lastBoard {}; set lastHands {}
}
proc clockText {ms} {
    set negative [expr $ms < 0]
    set n [expr int(abs($ms)/1000)]
    if {$negative} {set prefix -} else {set prefix {}}
    return [format "%s%02d:%02d" $prefix [expr $n/60] [expr $n%60]]
}
proc snapshot {fields} {
    global turn active board hands status player0 player1 ply view lastBoard lastHands selected selectedDrop promotion
    set turn [lindex $fields 1]; set active [lindex $fields 2]; set canDeclare [lindex $fields 3]
    set board [split [lindex $fields 6] ,]; set hands [split [lindex $fields 7] ,]
    set status [lindex $fields 8];set ply [lindex $fields 11]
    set side0 [lindex $fields 9]; set side1 [lindex $fields 10]
    if {$side0} {set player0 ai} else {set player0 human}
    if {$side1} {set player1 ai} else {set player1 human}
    if {$view != "game"} {return}
    foreach side {0 1} {
        set ms [lindex $fields [expr 4+$side]]
        .top.t$side configure -text [clockText $ms]
        if {$side == $turn && $active} {set bg #fff3bd} else {set bg #d9d9d9}
        if {$ms < 0} {set fg #a00000} else {set fg black}
        .top.t$side configure -background $bg -foreground $fg
    }
    if {$board != $lastBoard || $hands != $lastHands} {
        set selected -1;set selectedDrop 0;set lastBoard $board;set lastHands $hands;drawBoard
    }
    if {$canDeclare} {set action declare} else {set action resign}
    .bottom.action configure -bitmap [bm $action]
    if {$active} {
        .bottom.action configure -state normal; .bottom.next configure -state disabled
        if {$status == "engine_starting"} {set label starting} elseif {[set player$turn] == "ai"} {set label thinking} elseif {$status == "check"} {set label check} else {set label choose}
    } else {
        .bottom.action configure -state disabled; .bottom.next configure -state normal
        if {[string match sente_wins* $status] || [string match gote_loses* $status]} {set label sente_win} elseif {[string match gote_wins* $status] || [string match sente_loses* $status]} {set label gote_win} elseif {[string match draw* $status]} {set label draw} else {set label failure}
        if {[winfo exists .promotion]} {grab release .promotion; destroy .promotion;set promotion {}}
    }
    .bottom.status configure -bitmap [bm $label] -text {}
    debugState $fields
}
proc drawBoard {} {
    global board hands selected selectedDrop turn
    set c .body.board; $c delete all
    # Opponent hand, board, then sente hand. Files descend from 9 to 1.
    foreach s {1 0} {
        if {$s} {set y 16} else {set y 441}
        for {set p 1} {$p <= 7} {incr p} {
            set x [expr 25+($p-1)*57];set n [lindex $hands [expr $s*7+$p-1]]
            if {$n == ""} {set n 0}
            if {$n > 0} {set color black} else {set color #aaaaaa}
            if {$selectedDrop == $p && $s == $turn} {$c create rectangle [expr $x-20] [expr $y-16] [expr $x+32] [expr $y+20] -fill #fff3bd -outline #b39138}
            $c create bitmap $x $y -bitmap [bm piece${p}_0] -foreground $color
            $c create text [expr $x+23] $y -font fixed -text $n -fill $color
        }
    }
    $c create rectangle 20 50 398 428 -fill #eee0b7 -outline #705c36
    for {set i 0} {$i < 9} {incr i} {
        set x [expr 20+$i*42]; set y [expr 50+$i*42]
        $c create text [expr $x+21] 41 -font fixed -text [expr 9-$i]
        $c create bitmap 414 [expr $y+21] -bitmap [bm rank[expr $i+1]]
        if {$i} {$c create line $x 50 $x 428 -fill #705c36; $c create line 20 $y 398 $y -fill #705c36}
    }
    if {$selected >= 0} {
        set x [expr 20+($selected%9)*42];set y [expr 50+($selected/9)*42]
        $c create rectangle [expr $x+1] [expr $y+1] [expr $x+41] [expr $y+41] -fill #fff5b8 -outline #a07000 -width 2
    }
    for {set i 0} {$i < 81} {incr i} {
        set p [lindex $board $i]; if {$p == "" || $p == 0} {continue}
        set s [expr $p<0];set p [expr abs($p)]
        set x [expr 41+($i%9)*42];set y [expr 71+($i/9)*42]
        if {$p > 8} {set fg #9a250e} else {set fg black}
        $c create bitmap $x $y -bitmap [bm piece${p}_$s] -foreground $fg
    }
}
proc click {x y} {
    global active turn player0 player1 status board hands selected selectedDrop targets promotion
    if {!$active || [set player$turn] != "human" || $status == "engine_starting" || [winfo exists .promotion]} {return}
    # Hand selection is always the hand belonging to the current player.
    if {($turn == 0 && $y >= 425) || ($turn == 1 && $y < 35)} {
        set p [expr int(($x+3)/57)+1]
        if {$p >= 1 && $p <= 7 && [lindex $hands [expr $turn*7+$p-1]] > 0} {
            set selected -1;set selectedDrop $p;set targets {}; drawBoard;send "targets -1 $p"
        }
        return
    }
    if {$x < 20 || $x >= 398 || $y < 50 || $y >= 428} {return}
    set at [expr int(($y-50)/42)*9+int(($x-20)/42)]
    set p [lindex $board $at]
    if {$p != 0 && (($p < 0) == $turn)} {
        set selected $at;set selectedDrop 0;set targets {};drawBoard;send "targets $at 0"; return
    }
    if {$selected < 0 && !$selectedDrop} {return}
    set dest "[expr 9-$at%9][string index abcdefghi [expr $at/9]]"
    set choices {}
    foreach m $targets {if {[string range $m 2 3] == $dest} {lappend choices $m}}
    if {[llength $choices] == 2} {
        set promotion $choices
        toplevel .promotion; wm title .promotion "Promotion";wm transient .promotion .
        caption .promotion.label promote_question
        pack .promotion.label -padx 30 -pady 12
        frame .promotion.buttons;pack .promotion.buttons -pady 12
        button .promotion.buttons.yes -bitmap [bm yes] -command {choosePromotion 1}
        button .promotion.buttons.no -bitmap [bm no] -command {choosePromotion 0}
        button .promotion.buttons.cancel -bitmap [bm cancel] -command cancelPromotion
        pack .promotion.buttons.yes .promotion.buttons.no .promotion.buttons.cancel -side left -padx 8
        wm protocol .promotion WM_DELETE_WINDOW cancelPromotion
        grab set .promotion
    } elseif {[llength $choices] == 1} {send "move [lindex $choices 0]"} else {.bottom.status configure -bitmap [bm illegal]}
}
proc cancelPromotion {} {global promotion;grab release .promotion;destroy .promotion;set promotion {}}
proc choosePromotion {yes} {
    global promotion
    set chosen {}
    foreach m $promotion {if {([string length $m] == 5) == $yes} {set chosen $m}}
    cancelPromotion
    if {$chosen != ""} {send "move $chosen"}
}
proc addRecord {fields} {
    global records view
    lappend records $fields
    if {$view != "game"} {return}
    set c .body.record.list
    set n [lindex $fields 1];set s [lindex $fields 2];set f [lindex $fields 3];set r [lindex $fields 4]
    set p [lindex $fields 5];set pro [lindex $fields 6];set drop [lindex $fields 7]
    set y [expr ($n-1)*28+15]
    $c create text 22 $y -font fixed -text $n -anchor e -fill #777777
    $c create bitmap 36 $y -bitmap [bm side$s]
    $c create text 52 $y -font fixed -text $f
    $c create bitmap 69 $y -bitmap [bm rank$r]
    $c create bitmap 98 $y -bitmap [bm name$p]
    if {$pro} {$c create bitmap 130 $y -bitmap [bm promoted]}
    if {$drop} {$c create bitmap 130 $y -bitmap [bm drop]}
    if {!$drop} {$c create text 165 $y -anchor w -font fixed -text "([lindex $fields 8][lindex $fields 9])" -fill #777777}
    $c configure -scrollregion [list 0 0 244 [expr $n*28+4]]
    $c yview moveto 1
}
proc connectionLost {} {
    global active status channel view
    set active 0;set status engine_disconnected
    catch {fileevent $channel readable {}}
    if {$view == "game"} {
        .bottom.status configure -bitmap [bm failure]
        .bottom.action configure -state disabled
        .bottom.next configure -state disabled
    }
}
proc receive {} {
    global channel records view
    if {[eof $channel]} {connectionLost;return}
    if {[gets $channel line] < 0} {return}
    set kind [lindex $line 0]
    if {$kind == "state"} {snapshot $line} elseif {$kind == "move"} {addRecord $line} elseif {$kind == "targets"} {
        global targets;set targets [lrange $line 1 end]
    } elseif {$kind == "reset"} {
        set records {};if {$view == "game"} {.body.record.list delete all}
    } elseif {$kind == "error" && $view == "game"} {.bottom.status configure -bitmap [bm illegal]}
}
# Debug commands use the actual widget handlers. No Tcl eval or network listener.
proc debugRead {} {
    global debugChannel
    if {[gets $debugChannel line] < 0} {return}
    set cmd [lindex $line 0]
    switch $cmd {
        setup {
            global player0 player1 minutes increment
            set player0 [lindex $line 1];set player1 [lindex $line 2]
            set minutes [lindex $line 3];set increment [lindex $line 4]
        }
        start {startGame}
        settings {settings}
        click {click [lindex $line 1] [lindex $line 2]}
        promote {choosePromotion [lindex $line 1]}
        action {send action}
        core {send [lrange $line 1 end]}
        quit {shutdown}
    }
}
proc debugState {fields} {
    global env selected selectedDrop records promotion
    if {![info exists env(SHOGI_GUI_DEBUG)]} {return}
    set f [open "$env(SHOGI_GUI_DEBUG).state" w]
    puts $f $fields
    puts $f "selection $selected $selectedDrop"
    puts $f "records [llength $records] promotion [llength $promotion]"
    close $f
}
settings
fileevent $channel readable receive
if {[info exists env(SHOGI_GUI_DEBUG)]} {
    set debugChannel [open $env(SHOGI_GUI_DEBUG) r+]
    fileevent $debugChannel readable debugRead
}
