<div class=screen id=<<phonename>>>
<div class=phonename><b><<phonename>> <<add_text>></b></div>
<img src=<<screen>> class='screenshot' id ='<<phonename>>' adb ='<<adb_option>>'>
<div id=softbar>
<div id=softbutton><img src=static/back.png width=20px adb=<<adb_option>> class=backbutton origin=<<phonename>> title=Back></div>
<div id=softbutton><img src=static/home.png width=20px adb=<<adb_option>> class=homebutton origin=<<phonename>> title=Home></div>
<div id=softbutton><img src=static/gps.png width=20px adb=<<adb_option>> class=gpsbutton origin=<<phonename>> title="Set GPS position"></div>
<div id=softbutton><img src=static/keyboard.png width=20px adb=<<adb_option>> class=keyboardbutton origin=<<phonename>> title="Keyboard"></div>
<div id=softbutton><img src=static/download.png width=20px class=downloadbutton origin=<<phonename>> title="Download screen"></div>
</div>

<div class=phonename id=date<<phonename>>><<creationdate>></div>
<div id=button><a id=screenshot origin=<<phonename>> href='take_screenshot?origin=<<phonename>>&adb=<<adb_option>>'>Make Screenshot</a></div>
<div id=button><a href='quit_pogo?origin=<<phonename>>&adb=<<adb_option>>' id='quit' origin=<<phonename>>>Quit Pogo</a></div>
<div id=button><a href='restart_phone?origin=<<phonename>>&adb=<<adb_option>>'>Reboot Phone</a></div>
</div>