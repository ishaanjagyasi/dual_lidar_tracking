//file: OSCSend.pde
class OSCSender {

  void sendOSC() {
    OscMessage msg = new OscMessage("/cells");

    for (int row = 0; row < grid.rows; row++) {
      for (int col = 0; col < grid.cols; col++) {

        // If you still use the restricted-column mechanic anywhere, keep this:
        // if (isRestrictedColumnRound && col != 2) continue;

        GridCell c = grid.cells[row][col];
        //TO DO: modify this so it also sends current level 
        msg.add(c.number);
        msg.add(c.col);
        msg.add(c.row);
        msg.add(c.isUserHere ? 1 : 0);
        msg.add(c.isGlitching ? 1 : 0);
        if (row == 1 && col == 1 ) {
          println(c.isGlitching);
        }
        //msg.add(currentRound); // uncomment if you want to use this. must adjust MAX to accept a sixth argument.
      }
    }

    oscP5.send(msg, remoteAddress);
    
    //send scores to max 
    OscMessage msg2 = new OscMessage("/scores");
    msg2.add(scoreTracker.successPoints);
    msg2.add(scoreTracker.getConfidence());
    oscP5.send(msg2, remoteAddress);
    
    //send level to max
    OscMessage msg3 = new OscMessage("/level");
    msg3.add(currentRound);
    oscP5.send(msg3, remoteAddress);

  }
}
