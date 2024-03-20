import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
import vlc

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create VLC instance
        self.instance = vlc.Instance('--no-xlib')
        
        # Create media player
        self.player = self.instance.media_player_new()
        
        # Load media
        self.media = self.instance.media_new('/home/piswitch/Apps/sb-audio/2-Charlie_Calls_Olive.mp3')
        
        # Set media to player
        self.player.set_media(self.media)
        
        # Create caption label
        self.caption_label = QLabel()
        
        # Create layout
        layout = QVBoxLayout()
        layout.addWidget(self.caption_label)
        
        # Create central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Start playing the media
        self.player.play()
        
        # Start displaying captions
        self.display_captions('captions/2-Charlie_Calls_Olive.srt')

    def display_captions(self, caption_file):
        with open(caption_file, 'r') as f:
            captions = f.read().split('\n\n')

        def time_str_to_ms(time_str):
            hours, minutes, seconds_ms = time_str.split(':')
            seconds, milliseconds = seconds_ms.split(',')
            # Forget hours int(hours) * 3600000 + 
            return int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)

        for caption in captions:
            # print(f'full entry: {caption}')
            # if '-->' in caption:
            #     continue

            # Split the caption into time and text
            number, time, text = caption.split('\n', 2)
            print(f'time: {time}, text: {text}')

            # Update the caption label
            self.caption_label.setText(text)
            QApplication.processEvents()

            # Proccess time
            times = time.split(' --> ')
            # print(f'times[0]: {times[0]}')
            start_time_ms = time_str_to_ms(times[0])
            end_time_ms = time_str_to_ms(times[1])
            # Calculate the duration for which the caption should be displayed
            duration_ms = end_time_ms - start_time_ms
            

            # duration = int((float(time.split()[2].replace(',', '.')) - float(time.split()[0].replace(',', '.'))) * 1000)

            # Display the caption for the specified duration
            # self.player.set_time(int(float(time.split()[0].replace(',', '.')) * 1000))
            self.player.set_time(start_time_ms)
            QApplication.processEvents()

            # self.player.set_time(int(float(time.split()[0].replace(',', '.')) * 1000) + duration)
            self.player.set_time(end_time_ms + duration_ms)
            QApplication.processEvents()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
