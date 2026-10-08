; Freight Fate: hand the arrow keys straight to the game.
;
; JAWS binds the arrows to its own reading scripts in every application. In
; the game those scripts find no text to read, wait for the screen to change,
; and only then send the key on, about four times a second. Held arrows
; lag, and menus answer slowly. These overrides send the key on at once.
; The game speaks through JAWS itself; nothing here is spoken.

Include "hjconst.jsh"

Script SayPriorLine ()
TypeCurrentScriptKey ()
EndScript

Script SayNextLine ()
TypeCurrentScriptKey ()
EndScript

Script SayPriorCharacter ()
TypeCurrentScriptKey ()
EndScript

Script SayNextCharacter ()
TypeCurrentScriptKey ()
EndScript
