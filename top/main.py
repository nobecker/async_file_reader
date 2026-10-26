import json
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


OPTIONS = [f"OPTION_{number}" for number in range(1, 7)]
BOX_SIZE = 125
VISIBLE_BOXES = 4


class DragLabel(QLabel):
    """A draggable tile that can also act as a drop target."""

    MIME_TYPE = "application/x-option-wizard-option"

    def __init__(self, text: str, *, drop_callback=None, visibility_callback=None, parent=None):
        super().__init__(text, parent)
        self.drop_callback = drop_callback
        self.visibility_callback = visibility_callback
        self.drag_start = QPoint()
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(BOX_SIZE, BOX_SIZE)
        self.default_style = (
            "QLabel { background: #f2f5f8; border: 2px solid #9aa7b2; "
            "border-radius: 8px; font-size: 15px; font-weight: 600; }"
            "QLabel:hover { border-color: #2678c8; }"
        )
        self.setStyleSheet(self.default_style)
        self.setAcceptDrops(drop_callback is not None)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or not self.text():
            return
        if (event.pos() - self.drag_start).manhattanLength() < QApplication.startDragDistance():
            return
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, self.text().encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        preview = QPixmap(self.size())
        preview.fill(Qt.transparent)
        self.render(preview)
        drag.setPixmap(preview)
        drag.setHotSpot(event.pos())
        self.hide()
        drag.exec_(Qt.MoveAction | Qt.CopyAction, Qt.MoveAction)
        if self.visibility_callback is None:
            self.show()
        else:
            self.setVisible(self.visibility_callback())

    def dragEnterEvent(self, event):
        if self.drop_callback and event.mimeData().hasFormat(self.MIME_TYPE):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self.setStyleSheet(
                "QLabel { background: #c9f2d2; border: 3px solid #219653; "
                "border-radius: 8px; font-size: 15px; font-weight: 600; }"
            )
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.default_style)
        event.accept()

    def dropEvent(self, event):
        if self.drop_callback and event.mimeData().hasFormat(self.MIME_TYPE):
            option = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8")
            self.drop_callback(option)
            self.setStyleSheet(self.default_style)
            event.setDropAction(Qt.MoveAction)
            event.accept()


class OptionsDropPanel(QWidget):
    """Drop area for returning a placed option to the Options shelf."""

    MIME_TYPE = DragLabel.MIME_TYPE

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "OptionsDropPanel { background: #f8fafc; border: 2px dashed #9aa7b2; "
            "border-radius: 8px; }"
        )
        self.setMinimumHeight(2 * BOX_SIZE + 74)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            self.setStyleSheet(
                "OptionsDropPanel { background: #e8f7ec; border: 2px dashed #219653; "
                "border-radius: 8px; }"
            )
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "OptionsDropPanel { background: #f8fafc; border: 2px dashed #9aa7b2; "
            "border-radius: 8px; }"
        )
        event.accept()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            option = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8")
            self.callback(option)
            self.setStyleSheet(
                "OptionsDropPanel { background: #f8fafc; border: 2px dashed #9aa7b2; "
                "border-radius: 8px; }"
            )
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            event.ignore()


class OrderWizard(QWidget):
    def __init__(self, save_path: Path):
        super().__init__()
        self.save_path = save_path
        self.order = [None] * len(OPTIONS)
        self.page = 0
        self.page_count = (len(self.order) + VISIBLE_BOXES - 1) // VISIBLE_BOXES
        self.targets = []
        self.option_tiles = []

        root = QVBoxLayout(self)
        root.setSpacing(16)

        heading = QLabel("Arrange your options")
        heading.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(heading)
        root.addWidget(
            QLabel("Drag an option from Options into an arrangement. Drag it back to Options to remove it.")
        )
        proposed_heading = QLabel("Proposed arrangements")
        proposed_heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(proposed_heading, alignment=Qt.AlignHCenter)

        page_controls = QHBoxLayout()
        self.previous_button = QPushButton("← Previous")
        self.previous_button.clicked.connect(self.previous_page)
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self.next_page)
        page_controls.addWidget(self.previous_button)
        page_controls.addWidget(self.page_label, 1)
        page_controls.addWidget(self.next_button)
        root.addLayout(page_controls)

        self.box_row = QHBoxLayout()
        self.box_row.setSpacing(12)
        self.box_row.addStretch(1)
        for offset in range(VISIBLE_BOXES):
            target = DragLabel(
                "",
                drop_callback=lambda option, slot=offset: self.place_option(
                    self.page * VISIBLE_BOXES + slot, option
                ),
                visibility_callback=lambda slot=offset: (
                    self.page * VISIBLE_BOXES + slot < len(self.order)
                ),
            )
            target.default_style = (
                "QLabel { background: #e7f2ff; border: 2px solid #2678c8; "
                "border-radius: 8px; font-size: 15px; font-weight: 600; }"
                "QLabel:hover { background: #d7eaff; }"
            )
            target.setStyleSheet(target.default_style)
            self.box_row.addWidget(target)
            self.targets.append(target)
        self.box_row.addStretch(1)
        root.addLayout(self.box_row)

        self.options_panel = OptionsDropPanel(self.return_option)
        options_layout = QVBoxLayout(self.options_panel)
        options_heading = QLabel("Options — drop a proposed arrangement here to return it")
        options_heading.setAlignment(Qt.AlignCenter)
        options_heading.setStyleSheet("font-size: 16px; font-weight: 600; padding: 8px;")
        options_layout.addWidget(options_heading)
        options_content = QWidget()
        self.option_grid = QGridLayout(options_content)
        self.option_grid.setHorizontalSpacing(12)
        self.option_grid.setVerticalSpacing(12)
        for index, option in enumerate(OPTIONS):
            tile = DragLabel(
                option,
                drop_callback=self.return_option,
                visibility_callback=lambda name=option: name not in self.order,
            )
            self.option_grid.addWidget(tile, index // 3, index % 3)
            self.option_tiles.append(tile)
        options_layout.addWidget(options_content, alignment=Qt.AlignHCenter)
        root.addWidget(self.options_panel)
        self.feedback_label = QLabel("Drag an option tile into an empty proposed arrangement.")
        self.feedback_label.setStyleSheet("color: #425466; padding: 4px;")
        root.addWidget(self.feedback_label, alignment=Qt.AlignHCenter)

        footer = QHBoxLayout()
        footer.addStretch(1)
        save_button = QPushButton("Save configuration")
        save_button.clicked.connect(self.save_configuration)
        footer.addWidget(save_button)
        root.addLayout(footer)

        self.refresh_boxes()

    def refresh_boxes(self):
        start = self.page * VISIBLE_BOXES
        for offset, target in enumerate(self.targets):
            position = start + offset
            is_valid_position = position < len(self.order)
            target.setText(self.order[position] or "" if is_valid_position else "")
            target.setVisible(is_valid_position)
        self.refresh_options()
        self.page_label.setText(f"Page {self.page + 1} of {self.page_count}")
        self.previous_button.setEnabled(self.page > 0)
        self.next_button.setEnabled(self.page + 1 < self.page_count)

    def refresh_options(self):
        for tile in self.option_tiles:
            tile.setVisible(tile.text() not in self.order)

    def place_option(self, target_index: int, option: str):
        if option not in OPTIONS:
            return
        source_index = self.order.index(option) if option in self.order else None
        if self.order[target_index] is None:
            self.order[target_index] = option
            if source_index is not None and source_index != target_index:
                self.order[source_index] = None
            self.feedback_label.setText(f"Moved {option} to proposed arrangement {target_index + 1}.")
        else:
            replaced = self.order[target_index]
            if source_index is None:
                self.order[target_index] = option
                self.feedback_label.setText(
                    f"Placed {option} in arrangement {target_index + 1}; {replaced} returned to Options."
                )
            else:
                self.order[target_index], self.order[source_index] = (
                    self.order[source_index],
                    self.order[target_index],
                )
                self.feedback_label.setText(
                    f"Swapped {option} with {replaced} in proposed arrangement {target_index + 1}."
                )
        self.refresh_boxes()

    def return_option(self, option: str):
        if option not in self.order:
            return
        position = self.order.index(option)
        self.order[position] = None
        self.feedback_label.setText(
            f"Returned {option} from proposed arrangement {position + 1} to Options."
        )
        self.refresh_boxes()

    def previous_page(self):
        if self.page > 0:
            self.page -= 1
            self.refresh_boxes()

    def next_page(self):
        if self.page + 1 < self.page_count:
            self.page += 1
            self.refresh_boxes()

    def save_configuration(self):
        payload = {
            "proposed_arrangements": [
                {"position": position, "option": option}
                for position, option in enumerate(self.order)
            ]
        }
        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Save failed", f"Could not save configuration:\n{error}")
            return
        QMessageBox.information(self, "Saved", f"Configuration saved to:\n{self.save_path}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Option Order Wizard")
        self.setCentralWidget(OrderWizard(Path(__file__).with_name("configuration.json")))
        self.setMinimumWidth(780)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

