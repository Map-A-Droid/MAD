<div class="screen" id=<<phonename>>>
  <div class="phonename">
    <<phonename>> <<add_text>>
  </div>

  <img src="<<screen>>?cachebuster=<<time>>" class="screenshot" id="<<phonename>>" adb="<<adb_option>>">

  <div class="container-fluid softbar">
    <div class="row">
      <div class="col">
        <a href="#" class="backbutton" adb="<<adb_option>>" origin="<<phonename>>" title="Back button" data-toggle="tooltip"><i class="fas fa-chevron-left"></i></a>
      </div>
      <div class="col">
        <a href="#" class="homebutton" adb="<<adb_option>>" origin="<<phonename>>" title="Home button" data-toggle="tooltip"><i class="fas fa-home"></i></a>
      </div>
      <div class="col">
        <a href="#" class="gpsbutton" adb="<<adb_option>>" origin="<<phonename>>" title="Set custom location" data-toggle="tooltip"><i class="fas fa-map-marker-alt"></i></a>
      </div>
      <div class="col">
        <a href="#" class="keyboardbutton" adb="<<adb_option>>" origin="<<phonename>>" title="Send text to device" data-toggle="tooltip"><i class="fas fa-keyboard"></i></a>
      </div>
      <div class="col">
        <a href="#" class="downloadbutton" adb="<<adb_option>>" origin="<<phonename>>" title="Download screenshot" data-toggle="tooltip"><i class="fas fa-cloud-download-alt"></i></a>
      </div>
    </div>
  </div>

  <div class="infobar" id="date<<phonename>>">Last refresh: <span class="date" title="<<creationdate>>" data-toggle="tooltip"><<creationdate>></span></div>

  <div class="container-fluid controlButtons">
    <div class="row">
      <div class="col-md">
        <a href="take_screenshot?origin=<<phonename>>&adb=<<adb_option>>" class="action_screenshot" origin="<<phonename>>">Refresh screen</a>
      </div>
      <div class="col-md">
        <a href="clear_game_data?origin=<<phonename>>&adb=<<adb_option>>" class="confirm" origin="<<phonename>>" class="confirm" title="Do you really want to clear data for the game? This will result in the need to re-login">Reset game</a>
      </div>
    </div>
    <div class="row">
      <div class="col-md">
        <a href="quit_pogo?origin=<<phonename>>&adb=<<adb_option>>" class="action_quit" origin="<<phonename>>">Quit game</a>
      </div>
      <div class="col-md">
        <a href="restart_phone?origin=<<phonename>>&adb=<<adb_option>>" class="confirm" title="Do you really want to reboot the device?">Reboot device</a>
      </div>
    </div>
    <div class="row">
      <div class="col-md">
        <a href="uploaded_files?origin=<<phonename>>&adb=<<adb_option>>">Run job</a>
      </div>
      <div class="col-md">
        <a href="download_logcat?origin=<<phonename>>" id="logcat" class="confirm" title="Download logcat? This will take a moment">Get logcat</a>
      </div>
    </div>
  </div>
</div>
