import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QMimeData, QPoint, QRect
from PyQt5.QtGui import QColor, QDrag, QPainter, QPixmap
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


BOX_SIZE = 125
VISIBLE_BOXES = 4


@dataclass(frozen=True)
class ConfigurableTile:
    image: QPixmap
    title: str
    name: str


class DragLabel(QLabel):
    """A draggable tile that can also act as a drop target."""

    MIME_TYPE = "application/x-option-wizard-option"

    def __init__(
        self,
        tile: Optional[ConfigurableTile] = None,
        *,
        drop_callback=None,
        visibility_callback=None,
        proposed=False,
        parent=None,
    ):
        super().__init__(parent)
        self.tile = tile
        self.drop_callback = drop_callback
        self.visibility_callback = visibility_callback
        self.drag_start = QPoint()
        self.proposed = proposed
        self.drop_highlighted = False
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(BOX_SIZE, BOX_SIZE)
        self.setAcceptDrops(drop_callback is not None)

    @property
    def tile_name(self):
        return self.tile.name if self.tile else None

    def set_tile(self, tile: Optional[ConfigurableTile]):
        self.tile = tile
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bounds = self.rect().adjusted(1, 1, -1, -1)
        if self.drop_highlighted:
            background, border = QColor("#c9f2d2"), QColor("#219653")
        elif self.proposed:
            background, border = QColor("#e7f2ff"), QColor("#2678c8")
        else:
            background, border = QColor("#f2f5f8"), QColor("#9aa7b2")
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(bounds, 8, 8)

        if self.tile and not self.tile.image.isNull():
            image_box = bounds.adjusted(8, 8, -8, -8)
            image = self.tile.image.scaled(
                image_box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            image_x = bounds.center().x() - image.width() // 2
            image_y = bounds.center().y() - image.height() // 2
            painter.drawPixmap(image_x, image_y, image)

        title = self.tile.title if self.tile else ""
        if title:
            title_rect = QRect(bounds.left() + 3, bounds.bottom() - 29, bounds.width() - 6, 25)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 165) if self.tile and not self.tile.image.isNull() else background)
            painter.drawRoundedRect(title_rect, 4, 4)
            painter.setPen(Qt.white if self.tile and not self.tile.image.isNull() else QColor("#25313b"))
            painter.drawText(title_rect, Qt.AlignCenter, title)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(border if not self.drop_highlighted else QColor("#219653"))
        painter.drawRoundedRect(bounds, 8, 8)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or not self.tile_name:
            return
        if (event.pos() - self.drag_start).manhattanLength() < QApplication.startDragDistance():
            return
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, self.tile_name.encode("utf-8"))
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
            self.drop_highlighted = True
            self.update()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_highlighted = False
        self.update()
        event.accept()

    def dropEvent(self, event):
        if self.drop_callback and event.mimeData().hasFormat(self.MIME_TYPE):
            name = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8")
            self.drop_callback(name)
            self.drop_highlighted = False
            self.update()
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
    def __init__(self, tiles: list[ConfigurableTile], save_path: Path):
        super().__init__()
        if len({tile.name for tile in tiles}) != len(tiles):
            raise ValueError("ConfigurableTile names must be unique.")
        self.tiles = list(tiles)
        self.tiles_by_name = {tile.name: tile for tile in tiles}
        self.save_path = save_path
        self.order = [None] * len(self.tiles)
        self.page = 0
        self.page_count = max(1, (len(self.order) + VISIBLE_BOXES - 1) // VISIBLE_BOXES)
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
                drop_callback=lambda name, slot=offset: self.place_option(
                    self.page * VISIBLE_BOXES + slot, name
                ),
                visibility_callback=lambda slot=offset: (
                    self.page * VISIBLE_BOXES + slot < len(self.order)
                ),
                proposed=True,
            )
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
        for index, configurable_tile in enumerate(self.tiles):
            tile = DragLabel(
                configurable_tile,
                drop_callback=self.return_option,
                visibility_callback=lambda name=configurable_tile.name: name not in self.order,
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
            name = self.order[position] if is_valid_position else None
            target.set_tile(self.tiles_by_name.get(name))
            target.setVisible(is_valid_position)
        self.refresh_options()
        self.page_label.setText(f"Page {self.page + 1} of {self.page_count}")
        self.previous_button.setEnabled(self.page > 0)
        self.next_button.setEnabled(self.page + 1 < self.page_count)

    def refresh_options(self):
        for tile in self.option_tiles:
            tile.setVisible(tile.tile_name not in self.order)

    def place_option(self, target_index: int, name: str):
        if name not in self.tiles_by_name or not 0 <= target_index < len(self.order):
            return
        source_index = self.order.index(name) if name in self.order else None
        if self.order[target_index] is None:
            self.order[target_index] = name
            if source_index is not None and source_index != target_index:
                self.order[source_index] = None
            self.feedback_label.setText(
                f"Moved {self.tiles_by_name[name].title} to proposed arrangement {target_index + 1}."
            )
        else:
            replaced = self.order[target_index]
            if source_index is None:
                self.order[target_index] = name
                self.feedback_label.setText(
                    f"Placed {self.tiles_by_name[name].title} in arrangement {target_index + 1}; "
                    f"{self.tiles_by_name[replaced].title} returned to Options."
                )
            else:
                self.order[target_index], self.order[source_index] = (
                    self.order[source_index],
                    self.order[target_index],
                )
                self.feedback_label.setText(
                    f"Swapped {self.tiles_by_name[name].title} with "
                    f"{self.tiles_by_name[replaced].title} in proposed arrangement {target_index + 1}."
                )
        self.refresh_boxes()

    def return_option(self, name: str):
        if name not in self.order:
            return
        position = self.order.index(name)
        self.order[position] = None
        self.feedback_label.setText(
            f"Returned {self.tiles_by_name[name].title} from proposed arrangement {position + 1} to Options."
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
        sample_tiles = []
        colors = ["#4d83c7", "#57a773", "#e29a4a", "#9b75c7", "#d26d72", "#4da9ad"]
        for number, color in enumerate(colors, start=1):
            image = QPixmap(BOX_SIZE, BOX_SIZE)
            image.fill(QColor(color))
            sample_tiles.append(
                ConfigurableTile(image=image, title=f"OPTION_{number}", name=f"OPTION_{number}")
            )
        self.setCentralWidget(
            OrderWizard(sample_tiles, Path(__file__).with_name("configuration.json"))
        )
        self.setMinimumWidth(780)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

