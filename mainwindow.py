# This Python file uses the following encoding: utf-8
# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py

import sys
import sqlcipher3
import os.path
from os import makedirs
from shutil import copyfile
from mimetypes import guess_type
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QDialog, QTextEdit, QMessageBox, QListWidgetItem
from PySide6.QtWidgets import QWidget, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QInputDialog, QLineEdit
from PySide6.QtGui import QPalette, QPixmap, QImage, QColorSpace, QGuiApplication, QImageReader, QImageWriter, QKeySequence, QPainter, QPixmap, QFont
from PySide6.QtCore import QDir, QStandardPaths, Qt, Slot, QByteArray, QBuffer, QIODevice
from models import Base, Document, Text, Image, Attachment, DocumentText, DocumentImage, DocumentAttachment
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session
from ui_mainwindow import Ui_MainWindow
from ui_add_note_dialog import Ui_Dialog as Ui_AddNoteDialog
from ui_about_dialog import Ui_Dialog as Ui_AboutDialog
from ui_tab import Ui_Form as Ui_Tab

class ViewImageDialog(QDialog):
    def __init__(self, parent=None):
        super(ViewImageDialog, self).__init__(parent)
        self.setWindowTitle("Просмотр изображения")
        self.layout = QVBoxLayout()
        self.image_label = QLabel()
        self.image_label.setBackgroundRole(QPalette.Base)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_label.setScaledContents(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(QPalette.Dark)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setVisible(False)
        self.layout.addWidget(self.scroll_area)
        self.setLayout(self.layout)

    def set_image(self, new_image):
        self.image = new_image
        if self.image.colorSpace().isValid():
            self.image.convertToColorSpace(QColorSpace.SRgb)
        self.image_label.setPixmap(QPixmap.fromImage(self.image))
        self.scale_factor = 1.0
        self.scroll_area.setVisible(True)
        self.image_label.adjustSize()
        w = self.image.width()
        h = self.image.height()
        d = self.image.depth()
        color_space = self.image.colorSpace()
        description = color_space.description() if color_space.isValid() else 'unknown'
        message = f'Opened image, {w}x{h}, Depth: {d} ({description})'

class ViewAttachmentDialog(QDialog):
    def __init__(self, parent=None):
        super(ViewAttachmentDialog, self).__init__(parent)
        self.setWindowTitle("Просмотр приложения")
        self.layout = QVBoxLayout()
        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.layout.addWidget(self.textEdit)
        self.setLayout(self.layout)

    def set_content(self, content):
        self.textEdit.setPlainText(content)

class Tab(QWidget):
    def __init__(self, parent=None):
        super(Tab, self).__init__(parent)
        self.ui = Ui_Tab()
        self.ui.setupUi(self)
        self.ui.list_widget_images.itemDoubleClicked.connect(parent.show_image)
        self.ui.list_widget_attachments.itemDoubleClicked.connect(parent.show_attachment)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.ui = Ui_AboutDialog()
        self.ui.setupUi(self)
class AddNoteDialog(QDialog):
    def __init__(self, parent=None):
        super(AddNoteDialog, self).__init__(parent)
        self.ui = Ui_AddNoteDialog()
        self.ui.setupUi(self)

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.viewImageDialog = ViewImageDialog(self)
        self.viewAttachmentDialog = ViewAttachmentDialog(self)
        self.addNoteDialog = AddNoteDialog(self)
        self.aboutDialog = AboutDialog(self)
        self.current_path = ''
        self.previous_paths = []
        self.previous_paths_actions = []
        self._font = QFont()
        self.session, self.engine = None, None

        self.ui.tabWidget.clear()
        self.ui.menu_recent.clear()
        self.load_previous()
        self.setAcceptDrops(True)

        self.addNoteDialog.accepted.connect(self.add_note)

        self.ui.action_open_database.triggered.connect(self.open_db)
        self.ui.action_create_database.triggered.connect(self.create_db)
        self.ui.action_create_note.triggered.connect(self.addNoteDialog.open)
        self.ui.action_save.triggered.connect(self.save)
        self.ui.action_save_as.triggered.connect(self.save_as)
        self.ui.action_close.triggered.connect(self.close_connection)
        self.ui.action_exit.triggered.connect(self.close_window)
        self.ui.action_export_note.triggered.connect(self.export_note)
        self.ui.action_import_note.triggered.connect(self.import_note)

        self.ui.action_copy.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.copy())
        self.ui.action_paste.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.paste())
        self.ui.action_undo.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.undo())
        self.ui.action_redo.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.redo())
        self.ui.action_cut.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.cut())
        self.ui.action_select_all.triggered.connect(lambda _: self.ui.tabWidget.currentWidget().ui.textEdit.selectAll())

        self.ui.action_format.toggled.connect(self.set_format)
        self.ui.action_swap_colors.toggled.connect(self.swap_colors)
        self.ui.action_fullscreen.toggled.connect(lambda x: self.showFullScreen() if x else self.showNormal())
        self.ui.action_decrease_text.triggered.connect(self.decrease_font_size)
        self.ui.action_increase_text.triggered.connect(self.increase_font_size)

        self.ui.action_about_program.triggered.connect(self.aboutDialog.open)

    def swap_colors(self, state):
        if state:
            self.setStyleSheet("background-color: black; color: white")
        else:
            self.setStyleSheet("")
    def increase_font_size(self):
        print(self._font.pointSize())
        if self._font.pointSize()<50:
            self._font.setPointSize(self._font.pointSize()+1)
            self.setFont(self._font)
        print(self._font.pointSize())

    def decrease_font_size(self):
        print(self._font.pointSize())
        if self._font.pointSize()>5:
            self._font.setPointSize(self._font.pointSize()-1)
            self.setFont(self._font)
        print(self._font.pointSize())

    def import_note(self):
        dialog = QFileDialog(self, "Импортировать")
        locations = QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)
        directory = locations[-1] if locations else QDir.currentPath()
        dialog.setDirectory(directory)
        filters = ["Markdown files (*.txt *.md)", "Any files (*)"]
        dialog.setNameFilters(filters)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setDefaultSuffix("md")
        if (dialog.exec() == QDialog.Accepted):
            name = os.path.basename(dialog.selectedFiles()[0])
            contents = ''
            with open(dialog.selectedFiles()[0], 'rt') as file:
                contents = file.read()
            try:
                document = Document(name=name)
                text = Text(text=contents)
                self.session.add(document)
                self.session.add(text)
                self.session.commit()
                document_text = DocumentText(document_id=document.id, text_id=text.id)
                self.session.add(document_text)
                self.session.commit()
                self.save()
                self.sync_notes()
            except SQLAlchemyError as e:
                print(e)
                self.session.rollback()
            print(name)

    def export_note(self):
        dialog = QFileDialog(self, "Экспортировать")
        locations = QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)
        directory = locations[-1] if locations else QDir.currentPath()
        dialog.setDirectory(directory)
        filters = ["Markdown files (*.txt *.md)", "Any files (*)"]
        dialog.setNameFilters(filters)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDefaultSuffix("md")
        if (dialog.exec() == QDialog.Accepted):
            self.save()
            document = self.session.query(Document).filter(Document.name==self.ui.tabWidget.tabText(self.ui.tabWidget.currentIndex())).one()
            if document is None:
                return
            content = ''
            for text in document.document_texts:
                content += text.text.text
            with open(dialog.selectedFiles()[0], 'wt') as file:
                file.write(content)
            dir = os.path.dirname(dialog.selectedFiles()[0])
            if len(document.document_images) > 0:
                if not os.path.isdir(os.path.join(dir, 'images')):
                    makedirs(os.path.join(dir, 'images'))
                for index, image in enumerate(document.document_images):
                    with open(os.path.join(dir, 'images', f'{index}.png'), 'wb') as file:
                        file.write(image.image.image)
            if len(document.document_attachments) > 0:
                if not os.path.isdir(os.path.join(dir, 'attachments')):
                    makedirs(os.path.join(dir, 'attachments'))
                for index, attachment in enumerate(document.document_attachments):
                    with open(os.path.join(dir, 'attachments', f'{index}.png'), 'wt') as file:
                        file.write(attachment.attachment.text)

    def save_as(self):
        dialog = QFileDialog(self, "Сохранить как")
        locations = QStandardPaths.standardLocations(QStandardPaths.DownloadLocation)
        directory = locations[-1] if locations else QDir.currentPath()
        dialog.setDirectory(directory)
        filters = ["Database files (*.db *.sqlite3)", "Any files (*)"]
        dialog.setNameFilters(filters)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDefaultSuffix("db")
        if (dialog.exec() == QDialog.Accepted):
            self.save()
            copyfile(self.current_path, dialog.selectedFiles()[0])

    def add_to_prev_connected(self, path):
        if not os.path.isfile('prev.txt'):
            with open('prev.txt', 'wt') as file:
                file.write(path)
        else:
            in_it = False
            with open('prev.txt', 'rt') as file:
                for line in file:
                    if path == line:
                        in_it = True
                        break
            if not in_it:
                with open('prev.txt', 'at') as file:
                    file.write('\n'+path)

    def load_previous(self):
        if os.path.isfile('prev.txt'):
            with open('prev.txt', 'rt') as file:
                for line in file:
                    self.previous_paths.append(line.strip())
                    action = self.ui.menu_recent.addAction(f'&{line.strip()}')
                    action.triggered.connect(lambda: self.connect_to_db(line.strip(), False))
                    self.previous_paths.append(action)

    def show_image(self, image_item):
        document_image = self.session.query(DocumentImage).filter(DocumentImage.id==int(image_item.toolTip())).one_or_none()
        if not document_image:
            return
        image_bytes = document_image.image.image
        image_obj = QPixmap()
        image_obj.loadFromData(image_bytes, "PNG")
        image_obj = image_obj.toImage()
        self.viewImageDialog.set_image(image_obj)
        self.viewImageDialog.show()

    def show_attachment(self, attachment_item):
        document_attachment = self.session.query(DocumentAttachment).filter(DocumentAttachment.id==int(attachment_item.toolTip())).one_or_none()
        if not document_attachment:
            return
        self.viewAttachmentDialog.set_content(document_attachment.attachment.text)
        self.viewAttachmentDialog.show()

    def set_format(self, enabled):
        if None in (self.engine, self.session):
            return
        if enabled:
            text = self.ui.tabWidget.currentWidget().ui.textEdit.toPlainText()
            self.ui.tabWidget.currentWidget().ui.textEdit.setMarkdown(text)
        else:
            text = self.ui.tabWidget.currentWidget().ui.textEdit.toMarkdown()
            self.ui.tabWidget.currentWidget().ui.textEdit.setPlainText(text)

    def dragEnterEvent(self, event):
        if None in (self.engine, self.session):
            return
        print(event.mimeData().formats())
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def load_image(self, url):
        reader = QImageReader(url)
        reader.setAutoTransform(True)
        new_image = reader.read()
        if new_image.isNull():
            error = reader.errorString()
            QMessageBox.information(self, QGuiApplication.applicationDisplayName(),
                                    f"Cannot load {QDir.toNativeSeparators(url)}: {error}")
            return
        try:
            pixmap = QPixmap.fromImage(new_image)
            bytes = QByteArray()
            buffer = QBuffer(bytes)
            buffer.open(QIODevice.WriteOnly)
            pixmap.save(buffer, "PNG")
            image = Image(image=bytes)
            self.session.add(image)
            self.session.commit()
            document = self.session.query(Document).filter(Document.name==self.ui.tabWidget.tabText(self.ui.tabWidget.currentIndex())).one()
            document_image = DocumentImage(document_id=document.id, image_id=image.id)
            self.session.add(document_image)
            self.session.commit()
            self.save()
            self.sync_notes()
        except SQLAlchemyError as e:
            print(e)
            self.session.rollback()

    def load_attachment(self, url):
        with open(url, 'rb') as file:
            try:
                attachment_bytes = file.read()
                attachment = Attachment(text=attachment_bytes.decode('utf-8'))
                self.session.add(attachment)
                self.session.commit()
                document = self.session.query(Document).filter(Document.name==self.ui.tabWidget.tabText(self.ui.tabWidget.currentIndex())).one()
                document_attachment = DocumentAttachment(document_id=document.id, attachment_id=attachment.id)
                self.session.add(document_attachment)
                self.session.commit()
                self.save()
                self.sync_notes()
            except SQLAlchemyError as e:
                print(e)
                self.session.rollback()

    def dropEvent(self, event):
        if not event.mimeData().urls()[0].isLocalFile():
            return
        url = event.mimeData().urls()[0].toLocalFile()
        mime, _ = guess_type(url)
        if mime.split('/')[0] == 'image':
            self.load_image(url)
        else:
            self.load_attachment(url)
        # self.viewImageDialog.exec()
        print(event.mimeData().text())

    def create_db(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)
        strFile = dialog.getSaveFileName(None, "Создать базу данных","","База данных (*.db *.sqlite *.sqlite3)")
        if strFile[0] != '':
            self.connect_to_db(strFile[0], True)

    def open_db(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.AnyFile)
        strFile = dialog.getOpenFileName(None, "Открыть базу данных","","База данных (*.db *.sqlite *.sqlite3)")
        if strFile[0] != '':
            self.connect_to_db(strFile[0], False)

    def connect_to_db(self, path, create_new):
        print(path)
        if not (create_new or os.path.isfile(path)):
            return
        password, ok = QInputDialog.getText(self, "Введите пароль для базы данных",
                                        "Password:", QLineEdit.Password)
        if ok and password:
            try:
                self.engine = create_engine(f'sqlite+pysqlcipher://:{password}@//{path}?cipher=aes-256-cfb&kdf_iter=64000', echo=True)
                self.session = sessionmaker(bind=self.engine)()
                self.current_path = path
                Base.metadata.create_all(bind=self.engine)
                self.add_to_prev_connected(path)
                self.sync_notes()
                self.action_toggle(True)
            except SQLAlchemyError as e:
                msgBox = QMessageBox()
                msgBox.setText("Произошла ошибка при открытии базы данных. \nПроверьте, что вы ввели правильный пароль.")
                msgBox.exec()

    def action_toggle(self, enable):
        self.ui.action_close.setEnabled(enable)
        self.ui.action_create_database.setEnabled(enable)
        self.ui.action_create_note.setEnabled(enable)
        self.ui.action_save.setEnabled(enable)
        self.ui.action_save_as.setEnabled(enable)
        self.ui.action_import_note.setEnabled(enable)
        self.ui.action_export_note.setEnabled(enable)

        self.ui.action_copy.setEnabled(enable)
        self.ui.action_paste.setEnabled(enable)
        self.ui.action_undo.setEnabled(enable)
        self.ui.action_redo.setEnabled(enable)
        self.ui.action_cut.setEnabled(enable)
        self.ui.action_select_all.setEnabled(enable)

    def close_connection(self):
        if None in (self.engine, self.session):
            return
        self.session.close()
        self.engine.dispose()
        self.current_path = ''
        self.session, self.engine = None, None
        self.ui.tabWidget.clear()
        self.action_toggle(False)

    def close_window(self):
        self.close_connection()
        QApplication.closeAllWindows()

    def add_note(self):
        if None in (self.engine, self.session):
            return
        name = self.addNoteDialog.ui.lineEdit.text()
        try:
            document = Document(name=name)
            text = Text(text='')
            self.session.add(document)
            self.session.add(text)
            self.session.commit()
            document_text = DocumentText(document_id=document.id, text_id=text.id)
            self.session.add(document_text)
            self.session.commit()
            self.save()
            self.sync_notes()
        except SQLAlchemyError as e:
            print(e)
            self.session.rollback()
        print(name)

    def sync_notes(self):
        if None in (self.engine, self.session):
            return
        current_tab = self.ui.tabWidget.currentIndex()
        self.ui.tabWidget.clear()
        documents = self.session.query(Document).all()
        for document in documents:
            texts = document.document_texts
            images = document.document_images
            attachments = document.document_attachments
            tab = Tab(self)
            content = ''
            for text in texts:
                content += text.text.text
            for image in images:
                item = QListWidgetItem(image.image.created_at.strftime("%c"))
                item.setToolTip(str(image.id))
                tab.ui.list_widget_images.addItem(item)
            for attachment in attachments:
                item = QListWidgetItem(attachment.attachment.created_at.strftime("%c"))
                item.setToolTip(str(attachment.id))
                tab.ui.list_widget_attachments.addItem(item)
            tab.ui.textEdit.setPlainText(content)
            self.ui.tabWidget.addTab(tab, document.name)
        self.ui.tabWidget.setCurrentIndex(current_tab)

    def save(self):
        if None in (self.engine, self.session):
            return
        for i in range(self.ui.tabWidget.count()):
            tab = self.ui.tabWidget.widget(i)
            contents = ''
            if self.ui.action_format.isChecked():
                contents = tab.ui.textEdit.toMarkdown()
            else:
                contents = tab.ui.textEdit.toPlainText()
            document = self.session.query(Document).filter(Document.name==self.ui.tabWidget.tabText(i)).one()
            document.document_texts[0].text.text = contents
            self.session.commit()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
