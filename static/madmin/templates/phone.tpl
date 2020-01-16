<div class=screen id=<<phonename>>>
<div class=phonename><b><<phonename>> <<add_text>></b></div>
<img src=<<screen>>?cachebuster=<<time>> class='screenshot' id ='<<phonename>>' adb ='<<adb_option>>' >
<div id=softbar>
<div id=softbutton><img src=static/back.png width=20px adb=<<adb_option>> class=backbutton origin=<<phonename>> title=Back></div>
<div id=softbutton><img src=static/home.png width=20px adb=<<adb_option>> class=homebutton origin=<<phonename>> title=Home></div>
<div id=softbutton><img src=static/gps.png width=20px adb=<<adb_option>> class=gpsbutton origin=<<phonename>> title="Set GPS position"></div>
<div id=softbutton><img src=static/keyboard.png width=20px adb=<<adb_option>> class=keyboardbutton origin=<<phonename>> title="Keyboard"></div>
<div id=softbutton><img src=static/download.png width=20px class=downloadbutton origin=<<phonename>> title="Download screen"></div>
</div>

<div class=phonename id=date<<phonename>>><<creationdate>></div>
<div id=button><a id=screenshot origin=<<phonename>> href='take_screenshot?origin=<<phonename>>&adb=<<adb_option>>'>Take Screenshot</a></div>
<div id=button><a href='clear_game_data?origin=<<phonename>>&adb=<<adb_option>>' id='resetgamedata' origin=<<phonename>> class='confirm' title='Do you really want to clear data for pogo, this will result in the need to re-login?'>Reset Game Data</a></div>
<div id=button><a href='quit_pogo?origin=<<phonename>>&adb=<<adb_option>>' id='quit' origin=<<phonename>>>Quit Pogo</a></div>
<div id=button><a href='restart_phone?origin=<<phonename>>&adb=<<adb_option>>' class='confirm' title='Do you really want to restart the device?'>Reboot device</a></div>
<div id=button><a href='uploaded_files?origin=<<phonename>>&adb=<<adb_option>>'>Process Job</a></div>
</div>
