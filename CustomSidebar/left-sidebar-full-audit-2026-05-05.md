# Left Sidebar Full Audit Dump

## Summary
- Current sidebar width: `500px`.
- Rail navigation is icon-only with hover tooltips.
- Clipboard rows include full-message hover previews.
- Clipboard keyboard scrolling uses a direct `ListView` for reliable `positionViewAtIndex` behavior.
- Speaking includes elapsed recording time, recording pulse, transcribing loader, and Clean/Raw cleanup mode.
- Transcribed history is loaded from `~/.local/state/quickshell-speaking/history.json` through `Speaking.reloadHistory()`.
- Clean mode uses local Whisper plus Groq cleanup; Raw mode skips Groq.

## Backup And Verification
- Latest backup: `/home/rdp/.config/.codex-backups/sidebar-polish-20260505-101248`.
- `bash -n quickshell/ii/scripts/speaking/record-session.sh`: passed.
- `timeout 7s qs -c ii`: reached `Configuration Loaded`.
- Raw sample mode and Clean sample mode were run against the provided WhatsApp `.ogg` sample.

## Full Current Code

### `/home/rdp/.config/quickshell/ii/modules/ii/sidebarLeft/SidebarLeft.qml`

```qml
import qs
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import QtQuick
import Quickshell.Io
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland

Scope { // Scope
    id: root
    property bool detach: false
    property bool pin: false
    property real compactSidebarWidth: 500
    property Component contentComponent: SidebarLeftContent {}
    property Item sidebarContent

    function toggleDetach() {
        root.detach = !root.detach;
    }

    Process { // Dodge cursor away, pin, move cursor back
        id: pinWithFunnyHyprlandWorkaroundProc
        property var hook: null
        property int cursorX;
        property int cursorY;
        function doIt() {
            command = ["hyprctl", "cursorpos"]
            hook = (output) => {
                cursorX = parseInt(output.split(",")[0]);
                cursorY = parseInt(output.split(",")[1]);
                doIt2();
            }
            running = true;
        }
        function doIt2(output) {
            command = ["bash", "-c", "hyprctl dispatch movecursor 9999 9999"];
            hook = () => {
                doIt3();
            }
            running = true;
        }
        function doIt3(output) {
            root.pin = !root.pin;
            command = ["bash", "-c", `sleep 0.01; hyprctl dispatch movecursor ${cursorX} ${cursorY}`];
            hook = null
            running = true;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                pinWithFunnyHyprlandWorkaroundProc.hook(text);
            }
        }
    }

    function togglePin() {
        if (!root.pin) pinWithFunnyHyprlandWorkaroundProc.doIt()
        else root.pin = !root.pin;
    }

    Component.onCompleted: {
        root.sidebarContent = contentComponent.createObject(null, {
            "scopeRoot": root,
        });
        sidebarLoader.item.contentParent.children = [root.sidebarContent];
    }

    onDetachChanged: {
        if (root.detach) {
            GlobalFocusGrab.removeDismissable(sidebarLoader.item) // Remove sidebar from the focus grab system
            sidebarContent.parent = null; // Detach content from sidebar
            sidebarLoader.active = false; // Unload sidebar
            detachedSidebarLoader.active = true; // Load detached window
            detachedSidebarLoader.item.contentParent.children = [sidebarContent];
        } else {
            sidebarContent.parent = null; // Detach content from window
            detachedSidebarLoader.active = false; // Unload detached window
            sidebarLoader.active = true; // Load sidebar
            sidebarLoader.item.contentParent.children = [sidebarContent];
        }
    }

    Loader {
        id: sidebarLoader
        active: true
        
        sourceComponent: PanelWindow { // Window
            id: panelWindow
            visible: GlobalStates.sidebarLeftOpen
            
            property bool extend: true
            property real sidebarWidth: root.compactSidebarWidth
            property var contentParent: sidebarLeftBackground

            function hide() {
                GlobalStates.sidebarLeftOpen = false
            }

            exclusionMode: ExclusionMode.Normal
            exclusiveZone: root.pin ? sidebarWidth : 0
            implicitWidth: root.compactSidebarWidth + Appearance.sizes.elevationMargin
            WlrLayershell.namespace: "quickshell:sidebarLeft"
            // Hyprland 0.49: OnDemand is Exclusive, Exclusive just breaks click-outside-to-close
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
            color: "transparent"

            anchors {
                top: true
                left: true
                bottom: true
            }

            mask: Region {
                item: sidebarLeftBackground
            }

            onVisibleChanged: {
                if (visible) {
                    GlobalFocusGrab.addDismissable(panelWindow);
                } else {
                    GlobalFocusGrab.removeDismissable(panelWindow);
                }
            }
            Connections {
                target: GlobalFocusGrab
                function onDismissed() {
                    panelWindow.hide();
                }
            }

            // Content
            StyledRectangularShadow {
                target: sidebarLeftBackground
                radius: sidebarLeftBackground.radius
            }
            Rectangle {
                id: sidebarLeftBackground
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.topMargin: Appearance.sizes.hyprlandGapsOut
                anchors.leftMargin: Appearance.sizes.hyprlandGapsOut
                width: panelWindow.sidebarWidth - Appearance.sizes.hyprlandGapsOut - Appearance.sizes.elevationMargin
                height: parent.height - Appearance.sizes.hyprlandGapsOut * 2
                color: Appearance.colors.colLayer0
                border.width: 1
                border.color: Appearance.colors.colLayer0Border
                radius: Appearance.rounding.screenRounding - Appearance.sizes.hyprlandGapsOut + 1

                Behavior on width {
                    animation: Appearance.animation.elementMove.numberAnimation.createObject(this)
                }

                Keys.onPressed: (event) => {
                    if (event.key === Qt.Key_Escape) {
                        panelWindow.hide();
                    }
                    if (event.modifiers === Qt.ControlModifier) {
                        if (event.key === Qt.Key_O) {
                            panelWindow.extend = !panelWindow.extend;
                        } else if (event.key === Qt.Key_D) {
                            root.toggleDetach();
                        } else if (event.key === Qt.Key_P) {
                            root.togglePin();
                        }
                        event.accepted = true;
                    }
                }
            }
        }
    }

    Loader {
        id: detachedSidebarLoader
        active: false

        sourceComponent: FloatingWindow {
            id: detachedSidebarRoot
            property var contentParent: detachedSidebarBackground
            color: "transparent"

            visible: GlobalStates.sidebarLeftOpen
            onVisibleChanged: {
                if (!visible) GlobalStates.sidebarLeftOpen = false;
            }
            
            Rectangle {
                id: detachedSidebarBackground
                anchors.fill: parent
                color: Appearance.colors.colLayer0

                Keys.onPressed: (event) => {
                    if (event.modifiers === Qt.ControlModifier) {
                        if (event.key === Qt.Key_D) {
                            root.toggleDetach();
                        }
                        event.accepted = true;
                    }
                }
            }
        }
    }

    IpcHandler {
        target: "sidebarLeft"

        function toggle(): void {
            GlobalStates.sidebarLeftOpen = !GlobalStates.sidebarLeftOpen
        }

        function close(): void {
            GlobalStates.sidebarLeftOpen = false
        }

        function open(): void {
            GlobalStates.sidebarLeftOpen = true
        }
    }

    GlobalShortcut {
        name: "sidebarLeftToggle"
        description: "Toggles left sidebar on press"

        onPressed: {
            GlobalStates.sidebarLeftOpen = !GlobalStates.sidebarLeftOpen;
        }
    }

    GlobalShortcut {
        name: "sidebarLeftOpen"
        description: "Opens left sidebar on press"

        onPressed: {
            GlobalStates.sidebarLeftOpen = true;
        }
    }

    GlobalShortcut {
        name: "sidebarLeftClose"
        description: "Closes left sidebar on press"

        onPressed: {
            GlobalStates.sidebarLeftOpen = false;
        }
    }

    GlobalShortcut {
        name: "sidebarLeftToggleDetach"
        description: "Detach left sidebar into a window/Attach it back"

        onPressed: {
            root.detach = !root.detach;
        }
    }

}
```

### `/home/rdp/.config/quickshell/ii/modules/ii/sidebarLeft/SidebarLeftContent.qml`

```qml
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

Item {
    id: root
    required property var scopeRoot

    property int sidebarPadding: 8
    property string activeSection: "clipboard" // clipboard, pinned, images, history
    property string clipboardQuery: ""
    property int selectedClipIndex: -1
    property string selectedClipEntry: ""
    property var clipEntries: []
    property var historyEntries: []

    anchors.fill: parent
    focus: GlobalStates.sidebarLeftOpen

    onActiveSectionChanged: {
        root.selectedClipIndex = -1;
        root.selectedClipEntry = "";
        root.refreshModels();
        root.syncSelection();
    }
    onClipboardQueryChanged: root.refreshModels()
    onClipEntriesChanged: syncSelection()

    Component.onCompleted: {
        root.refreshModels();
        Speaking.reloadHistory();
    }

    Connections {
        target: GlobalStates
        function onSidebarLeftOpenChanged() {
            if (GlobalStates.sidebarLeftOpen) {
                root.forceActiveFocus();
                root.syncSelection();
            }
        }
    }

    Connections {
        target: Cliphist
        function onEntriesChanged() {
            root.refreshModels();
        }
    }

    Connections {
        target: PinnedClipboard
        function onEntriesChanged() {
            root.refreshModels();
        }
    }

    Connections {
        target: Speaking
        function onHistoryEntriesChanged() {
            root.refreshModels();
        }
    }

    function refreshModels() {
        root.clipEntries = root.filteredClipEntries();
        root.historyEntries = root.filteredHistoryEntries();
    }

    function clipText(entry): string {
        return StringUtils.cleanCliphistEntry(entry);
    }

    function clipType(entry): string {
        if (Cliphist.entryIsImage(entry))
            return "image";
        const text = clipText(entry).trim();
        if (/^https?:\/\//i.test(text))
            return "url";
        if (/^(git|sudo|cd|npm|pnpm|yarn|bun|docker|kubectl|ssh|pacman|yay|qs|hyprctl)\b/i.test(text))
            return "cmd";
        return "text";
    }

    function filteredClipEntries(): var {
        let entries = [];
        const q = root.clipboardQuery.trim().toLowerCase();
        if (root.activeSection === "pinned") {
            entries = PinnedClipboard.entries;
        } else if (root.activeSection === "images") {
            entries = Cliphist.entries.filter(entry => Cliphist.entryIsImage(entry));
        } else if (root.activeSection === "clipboard") {
            entries = Cliphist.entries.filter(entry => !Cliphist.entryIsImage(entry));
        } else {
            return [];
        }
        if (q.length > 0) {
            entries = entries.filter(entry => root.clipText(entry).toLowerCase().includes(q));
        }
        return entries.slice(0, 35);
    }

    function filteredHistoryEntries(): var {
        const q = root.clipboardQuery.trim().toLowerCase();
        let entries = Speaking.historyEntries;
        if (q.length > 0) {
            entries = entries.filter(item => {
                const cleaned = String(item.cleaned ?? "").toLowerCase();
                const raw = String(item.raw ?? "").toLowerCase();
                return cleaned.includes(q) || raw.includes(q);
            });
        }
        return entries.slice(0, 120);
    }

    function syncSelection() {
        if (root.activeSection === "history") {
            root.selectedClipIndex = -1;
            root.selectedClipEntry = "";
            return;
        }
        if (root.clipEntries.length === 0) {
            root.selectedClipIndex = -1;
            root.selectedClipEntry = "";
            return;
        }
        if (root.selectedClipEntry.length > 0) {
            const idx = root.clipEntries.indexOf(root.selectedClipEntry);
            if (idx >= 0) {
                root.selectedClipIndex = idx;
                root.ensureSelectionVisible();
                return;
            }
        }
        if (root.selectedClipIndex < 0 || root.selectedClipIndex >= root.clipEntries.length)
            root.selectedClipIndex = 0;
        root.selectedClipEntry = root.clipEntries[root.selectedClipIndex] ?? "";
        root.ensureSelectionVisible();
    }

    function selectRelative(delta) {
        if (root.activeSection === "history")
            return;
        if (root.clipEntries.length === 0)
            return;
        const base = root.selectedClipIndex < 0 ? 0 : root.selectedClipIndex;
        const next = Math.max(0, Math.min(root.clipEntries.length - 1, base + delta));
        root.selectedClipIndex = next;
        root.selectedClipEntry = root.clipEntries[next] ?? "";
        root.ensureSelectionVisible();
    }

    function selectIndex(index) {
        if (index < 0 || index >= root.clipEntries.length)
            return;
        root.selectedClipIndex = index;
        root.selectedClipEntry = root.clipEntries[index] ?? "";
        root.ensureSelectionVisible();
    }

    function ensureSelectionVisible() {
        if (root.selectedClipIndex < 0)
            return;
        if (typeof clipboardListView !== "undefined" && clipboardListView !== null)
            clipboardListView.positionViewAtIndex(root.selectedClipIndex, ListView.Contain);
    }

    function activateSelected() {
        if (root.activeSection === "history")
            return;
        if (root.selectedClipIndex < 0 || root.selectedClipIndex >= root.clipEntries.length)
            return;
        const entry = root.clipEntries[root.selectedClipIndex];
        root.selectedClipEntry = entry;
        Cliphist.paste(entry);
        GlobalStates.sidebarLeftOpen = false;
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Up) {
            root.selectRelative(-1);
            event.accepted = true;
            return;
        }
        if (event.key === Qt.Key_Down) {
            root.selectRelative(1);
            event.accepted = true;
            return;
        }
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && root.activeSection !== "history" && root.clipEntries.length > 0) {
            root.activateSelected();
            event.accepted = true;
            return;
        }
        if (event.key === Qt.Key_Escape) {
            GlobalStates.sidebarLeftOpen = false;
            event.accepted = true;
        }
    }

    component SectionTitle: StyledText {
        property string label
        text: label
        color: Appearance.colors.colSubtext
        font.pixelSize: Appearance.font.pixelSize.smaller
        font.family: Appearance.font.family.monospace
        font.letterSpacing: 1.1
    }

    component RailNavButton: RippleButton {
        id: button
        required property string section
        required property string iconName
        required property string label
        property bool selected: root.activeSection === section

        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 34
        Layout.preferredHeight: 34
        buttonRadius: 10
        toggled: selected
        colBackground: Qt.rgba(0.11, 0.11, 0.11, 0.7)
        colBackgroundHover: Qt.rgba(0.18, 0.18, 0.18, 0.82)
        colBackgroundToggled: Qt.rgba(0.28, 0.28, 0.28, 0.9)
        colBackgroundToggledHover: Qt.rgba(0.32, 0.32, 0.32, 0.94)
        onClicked: root.activeSection = section

        contentItem: Item {
            anchors.fill: parent
            MaterialSymbol {
                anchors.centerIn: parent
                text: button.iconName
                iconSize: 18
                fill: button.selected ? 1 : 0
                color: button.selected ? Appearance.colors.colOnLayer1 : Appearance.colors.colSubtext
            }
        }

        StyledToolTip {
            text: button.label
        }
    }

    component FullTextToolTip: PopupToolTip {
        id: fullTip
        required property string previewText
        extraVisibleCondition: false
        text: ""
        horizontalMargin: 0
        verticalMargin: 0
        anchorEdges: Edges.Right
        anchorGravity: Edges.Left
        contentItem: Rectangle {
            implicitWidth: 340
            implicitHeight: fullText.implicitHeight + 18
            radius: 10
            color: Appearance.colors.colTooltip
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.16)

            StyledText {
                id: fullText
                anchors {
                    left: parent.left
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                    leftMargin: 10
                    rightMargin: 10
                }
                text: fullTip.previewText
                color: Appearance.colors.colOnTooltip
                font.pixelSize: Appearance.font.pixelSize.smaller
                wrapMode: Text.Wrap
                maximumLineCount: 12
                elide: Text.ElideRight
            }
        }
    }

    component SearchField: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 34
        radius: 11
        color: Qt.rgba(0.08, 0.08, 0.08, 0.6)
        border.width: 1
        border.color: Qt.rgba(0.4, 0.4, 0.4, 0.22)

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 7

            MaterialSymbol {
                text: "search"
                iconSize: 18
                color: Appearance.colors.colSubtext
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: clipboardInput.text.length === 0
                    text: root.activeSection === "history" ? "Search transcribed history..." : "Search clipboard..."
                    color: Appearance.colors.colSubtext
                    font.pixelSize: Appearance.font.pixelSize.smaller
                }

                StyledTextInput {
                    id: clipboardInput
                    anchors.fill: parent
                    verticalAlignment: TextInput.AlignVCenter
                    font.pixelSize: Appearance.font.pixelSize.smaller
                    text: root.clipboardQuery
                    onTextChanged: root.clipboardQuery = text
                    Keys.onEscapePressed: root.clipboardQuery = ""
                }
            }
        }
    }

    component ClipboardRow: RippleButton {
        id: clipRow
        required property string entry
        required property int rowIndex

        property string displayText: root.clipText(entry)
        property string type: root.clipType(entry)
        property bool selected: root.selectedClipIndex === rowIndex
        property bool pinned: PinnedClipboard.isPinned(entry)

        width: ListView.view ? ListView.view.width : parent.width
        height: type === "image" ? 52 : 40
        buttonRadius: 10
        colBackground: clipRow.selected ? Qt.rgba(0.25, 0.25, 0.25, 0.8) : Qt.rgba(0.14, 0.14, 0.14, 0.68)
        colBackgroundHover: clipRow.selected ? Qt.rgba(0.31, 0.31, 0.31, 0.86) : Qt.rgba(0.2, 0.2, 0.2, 0.78)
        onClicked: {
            root.selectIndex(clipRow.rowIndex);
            root.activateSelected();
        }

        FullTextToolTip {
            previewText: clipRow.displayText
            alternativeVisibleCondition: clipRow.hovered && clipRow.displayText.length > 0
        }

        contentItem: RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 8
            spacing: 6

            Loader {
                active: clipRow.type === "image"
                visible: active
                sourceComponent: CliphistImage {
                    maxWidth: 36
                    maxHeight: 32
                    entry: clipRow.entry
                }
            }

            StyledText {
                Layout.fillWidth: true
                text: clipRow.displayText
                color: clipRow.type === "image" ? Appearance.colors.colSubtext : Appearance.colors.colOnLayer1
                font.family: clipRow.type === "cmd" ? Appearance.font.family.monospace : Appearance.font.family.main
                font.pixelSize: Appearance.font.pixelSize.smaller
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Rectangle {
                Layout.preferredWidth: Math.max(38, typeText.implicitWidth + 16)
                Layout.preferredHeight: 22
                radius: 7
                color: Qt.rgba(0.18, 0.18, 0.18, 0.72)
                border.width: 1
                border.color: Qt.rgba(0.58, 0.58, 0.58, 0.34)

                StyledText {
                    id: typeText
                    anchors.centerIn: parent
                    text: clipRow.type
                    color: Appearance.colors.colSubtext
                    font.pixelSize: Appearance.font.pixelSize.smaller
                }
            }

            RippleButton {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                buttonRadius: 7
                colBackground: Qt.rgba(0.16, 0.16, 0.16, 0.0)
                colBackgroundHover: Qt.rgba(0.3, 0.3, 0.3, 0.78)
                onClicked: PinnedClipboard.toggle(clipRow.entry)
                contentItem: MaterialSymbol {
                    text: "push_pin"
                    iconSize: 15
                    fill: clipRow.pinned ? 1 : 0
                    color: clipRow.pinned ? Appearance.colors.colOnLayer1 : Appearance.colors.colSubtext
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            RippleButton {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                buttonRadius: 7
                colBackground: Qt.rgba(0.16, 0.16, 0.16, 0.0)
                colBackgroundHover: Qt.rgba(0.3, 0.3, 0.3, 0.78)
                onClicked: {
                    Cliphist.deleteEntry(clipRow.entry);
                    root.syncSelection();
                }
                contentItem: MaterialSymbol {
                    text: "delete"
                    iconSize: 15
                    color: Appearance.colors.colSubtext
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    component HistoryRow: RippleButton {
        id: historyRow
        required property var itemData

        width: ListView.view ? ListView.view.width : parent.width
        height: 52
        buttonRadius: 10
        colBackground: Qt.rgba(0.14, 0.14, 0.14, 0.68)
        colBackgroundHover: Qt.rgba(0.2, 0.2, 0.2, 0.78)
        onClicked: Speaking.setTranscript(String(itemData.cleaned ?? ""))

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            anchors.topMargin: 6
            anchors.bottomMargin: 6
            spacing: 2

            StyledText {
                Layout.fillWidth: true
                text: String(itemData.cleaned ?? "").length > 0 ? String(itemData.cleaned) : String(itemData.raw ?? "")
                color: Appearance.colors.colOnLayer1
                font.pixelSize: Appearance.font.pixelSize.smaller
                elide: Text.ElideRight
                maximumLineCount: 1
            }
            StyledText {
                Layout.fillWidth: true
                text: String(itemData.timestamp ?? "")
                color: Appearance.colors.colSubtext
                font.pixelSize: Appearance.font.pixelSize.smaller
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }

    component SpeakingButton: RippleButton {
        id: speakingButton
        required property string label

        Layout.fillWidth: true
        Layout.preferredHeight: 30
        buttonRadius: 10
        colBackground: Qt.rgba(0.19, 0.19, 0.19, 0.86)
        colBackgroundHover: Qt.rgba(0.26, 0.26, 0.26, 0.9)
        opacity: enabled ? 1 : 0.34
        contentItem: StyledText {
            text: speakingButton.label
            color: Appearance.colors.colOnLayer1
            font.pixelSize: Appearance.font.pixelSize.smaller
            font.weight: Font.Medium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    component CleanupChoice: RippleButton {
        id: choice
        required property string modeName
        required property string label
        property bool selected: Speaking.cleanupMode === modeName

        Layout.preferredWidth: 58
        Layout.preferredHeight: 26
        buttonRadius: 8
        toggled: selected
        colBackground: Qt.rgba(0.11, 0.11, 0.11, 0.72)
        colBackgroundHover: Qt.rgba(0.2, 0.2, 0.2, 0.82)
        colBackgroundToggled: Qt.rgba(0.3, 0.3, 0.3, 0.9)
        colBackgroundToggledHover: Qt.rgba(0.36, 0.36, 0.36, 0.95)
        onClicked: Speaking.setCleanupMode(modeName)

        contentItem: RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 7
            anchors.rightMargin: 7
            spacing: 4

            Rectangle {
                Layout.preferredWidth: 8
                Layout.preferredHeight: 8
                radius: 999
                color: choice.selected ? Appearance.colors.colOnLayer1 : "transparent"
                border.width: 1
                border.color: choice.selected ? Appearance.colors.colOnLayer1 : Appearance.colors.colSubtext
            }

            StyledText {
                Layout.fillWidth: true
                text: choice.label
                color: choice.selected ? Appearance.colors.colOnLayer1 : Appearance.colors.colSubtext
                font.pixelSize: Appearance.font.pixelSize.smaller
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: root.sidebarPadding
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 44
            Layout.fillHeight: true
            radius: 15
            color: Qt.rgba(0.03, 0.03, 0.03, 0.94)
            border.width: 1
            border.color: Qt.rgba(0.42, 0.42, 0.42, 0.24)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 5
                spacing: 7

                RailNavButton {
                    section: "clipboard"
                    iconName: "content_paste"
                    label: "Clipboard"
                }
                RailNavButton {
                    section: "pinned"
                    iconName: "keep"
                    label: "Pinned"
                }
                RailNavButton {
                    section: "images"
                    iconName: "image"
                    label: "Images"
                }
                RailNavButton {
                    section: "history"
                    iconName: "history"
                    label: "Transcribed"
                }

                Item {
                    Layout.fillHeight: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 10
                    color: Qt.rgba(0.11, 0.11, 0.11, 0.86)
                    border.width: 1
                    border.color: Qt.rgba(0.42, 0.42, 0.42, 0.24)

                    MaterialSymbol {
                        anchors.centerIn: parent
                        text: Speaking.isActive ? "mic" : "mic_none"
                        iconSize: 16
                        color: Appearance.colors.colSubtext
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: Qt.rgba(0.12, 0.12, 0.12, 0.84)
                border.width: 1
                border.color: Qt.rgba(0.45, 0.45, 0.45, 0.3)
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    SectionTitle {
                        label: root.activeSection === "history" ? "TRANSCRIBED HISTORY" : "CLIPBOARD"
                    }

                    SearchField {}

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        ListView {
                            id: clipboardListView
                            anchors.fill: parent
                            visible: root.activeSection !== "history"
                            enabled: visible
                            clip: true
                            spacing: 6
                            boundsBehavior: Flickable.StopAtBounds
                            model: root.clipEntries
                            interactive: true
                            cacheBuffer: 900
                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                            delegate: ClipboardRow {
                                required property var modelData
                                required property int index
                                entry: modelData
                                rowIndex: index
                            }
                        }

                        ListView {
                            anchors.fill: parent
                            visible: root.activeSection === "history"
                            enabled: visible
                            clip: true
                            spacing: 6
                            boundsBehavior: Flickable.StopAtBounds
                            model: root.historyEntries
                            interactive: true
                            cacheBuffer: 700
                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                            delegate: HistoryRow {
                                required property var modelData
                                itemData: modelData
                            }
                        }

                        StyledText {
                            visible: root.activeSection !== "history" && root.clipEntries.length === 0
                            anchors.centerIn: parent
                            text: root.clipboardQuery.length > 0 ? "No matches" : (root.activeSection === "pinned" ? "No pinned clips" : "Clipboard history is empty")
                            color: Appearance.colors.colSubtext
                            font.pixelSize: Appearance.font.pixelSize.smaller
                        }

                        StyledText {
                            visible: root.activeSection === "history" && root.historyEntries.length === 0
                            anchors.centerIn: parent
                            text: root.clipboardQuery.length > 0 ? "No transcribed matches" : "No transcribed history yet"
                            color: Appearance.colors.colSubtext
                            font.pixelSize: Appearance.font.pixelSize.smaller
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 238
                radius: 16
                color: Qt.rgba(0.12, 0.12, 0.12, 0.84)
                border.width: 1
                border.color: Qt.rgba(0.45, 0.45, 0.45, 0.3)
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 7

                    RowLayout {
                        Layout.fillWidth: true
                        SectionTitle {
                            label: "SPEAKING"
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        StyledText {
                            text: Speaking.mode === "recording" ? `${Speaking.statusText} ${Speaking.formattedElapsed}` : Speaking.statusText
                            color: Appearance.colors.colSubtext
                            font.pixelSize: Appearance.font.pixelSize.smaller
                            elide: Text.ElideRight
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        radius: 9
                        color: Qt.rgba(0.08, 0.08, 0.08, 0.6)
                        border.width: 1
                        border.color: Qt.rgba(0.4, 0.4, 0.4, 0.2)

                        ComboBox {
                            id: micSelector
                            anchors.fill: parent
                            anchors.margins: 2
                            model: Speaking.inputDevices
                            textRole: "description"
                            currentIndex: {
                                for (let i = 0; i < Speaking.inputDevices.length; ++i) {
                                    const node = Speaking.inputDevices[i];
                                    if (node && node.name === Speaking.selectedSourceName)
                                        return i;
                                }
                                return -1;
                            }
                            delegate: ItemDelegate {
                                width: micSelector.width
                                contentItem: StyledText {
                                    text: modelData ? Audio.friendlyDeviceName(modelData) : ""
                                    font.pixelSize: Appearance.font.pixelSize.smaller
                                    color: Appearance.colors.colOnLayer1
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            contentItem: StyledText {
                                leftPadding: 8
                                rightPadding: 8
                                text: Speaking.selectedSourceLabel
                                color: Appearance.colors.colOnLayer1
                                font.pixelSize: Appearance.font.pixelSize.smaller
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 8
                                color: Qt.rgba(0.14, 0.14, 0.14, 0.8)
                                border.width: 1
                                border.color: Qt.rgba(0.4, 0.4, 0.4, 0.24)
                            }
                            onActivated: {
                                const node = Speaking.inputDevices[index];
                                if (node)
                                    Speaking.selectInputDeviceByName(String(node.name));
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        SpeakingButton {
                            label: "Start"
                            enabled: Speaking.canStart && !Speaking.controlsLocked
                            onClicked: Speaking.start()
                        }
                        SpeakingButton {
                            label: "Pause"
                            enabled: Speaking.canPause && !Speaking.controlsLocked
                            visible: Speaking.mode === "recording" || Speaking.mode === "paused"
                            onClicked: Speaking.pause()
                        }
                        SpeakingButton {
                            label: "Resume"
                            enabled: Speaking.canResume && !Speaking.controlsLocked
                            visible: Speaking.mode === "paused"
                            onClicked: Speaking.resume()
                        }
                        SpeakingButton {
                            label: "Stop"
                            enabled: Speaking.canStop && !Speaking.controlsLocked
                            onClicked: Speaking.stop()
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Rectangle {
                            Layout.preferredWidth: 30
                            Layout.preferredHeight: 26
                            radius: 8
                            color: Qt.rgba(0.1, 0.1, 0.1, 0.66)
                            border.width: 1
                            border.color: Qt.rgba(0.42, 0.42, 0.42, 0.24)

                            Rectangle {
                                id: recordPulse
                                anchors.centerIn: parent
                                width: Speaking.mode === "recording" ? 10 : 7
                                height: width
                                radius: 999
                                color: Appearance.colors.colOnLayer1
                                opacity: Speaking.mode === "recording" ? 0.85 : 0.32

                                SequentialAnimation on opacity {
                                    running: Speaking.mode === "recording"
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0.22; duration: 520 }
                                    NumberAnimation { to: 0.9; duration: 520 }
                                }
                            }

                            MaterialSymbol {
                                anchors.centerIn: parent
                                visible: Speaking.mode === "postprocessing"
                                text: "progress_activity"
                                iconSize: 17
                                color: Appearance.colors.colSubtext
                                RotationAnimation on rotation {
                                    running: Speaking.mode === "postprocessing"
                                    loops: Animation.Infinite
                                    from: 0
                                    to: 360
                                    duration: 1100
                                }
                            }
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: Speaking.mode === "postprocessing" ? "Transcribing..." : (Speaking.mode === "recording" ? `Audio ${Speaking.formattedElapsed}` : "Ready")
                            color: Appearance.colors.colSubtext
                            font.pixelSize: Appearance.font.pixelSize.smaller
                            elide: Text.ElideRight
                        }

                        CleanupChoice {
                            modeName: "groq"
                            label: "Clean"
                        }
                        CleanupChoice {
                            modeName: "raw"
                            label: "Raw"
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 11
                        color: Qt.rgba(0.08, 0.08, 0.08, 0.56)
                        border.width: 1
                        border.color: Qt.rgba(0.44, 0.44, 0.44, 0.24)
                        clip: true

                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 8
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded

                            TextArea {
                                id: transcriptText
                                text: Speaking.transcript.length > 0 ? Speaking.transcript : ""
                                placeholderText: "Transcribed text will appear here."
                                wrapMode: TextEdit.Wrap
                                color: Appearance.colors.colOnLayer1
                                font.pixelSize: Appearance.font.pixelSize.smaller
                                selectByMouse: true
                                background: Rectangle {
                                    color: "transparent"
                                }
                                onTextChanged: {
                                    if (text !== Speaking.transcript)
                                        Speaking.setTranscript(text);
                                }
                            }
                        }

                        RippleButton {
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 8
                            width: 28
                            height: 28
                            enabled: Speaking.transcript.length > 0
                            buttonRadius: 9
                            colBackground: Qt.rgba(0.19, 0.19, 0.19, 0.82)
                            colBackgroundHover: Qt.rgba(0.28, 0.28, 0.28, 0.9)
                            opacity: enabled ? 1 : 0.34
                            onClicked: Speaking.copyTranscript()
                            contentItem: MaterialSymbol {
                                text: "content_copy"
                                iconSize: 15
                                color: Appearance.colors.colSubtext
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }
        }
    }
}
```

### `/home/rdp/.config/quickshell/ii/services/PinnedClipboard.qml`

```qml
pragma Singleton
pragma ComponentBehavior: Bound

import qs.modules.common
import qs.modules.common.functions
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string stateDir: FileUtils.trimFileProtocol(`${Directories.state}/quickshell-sidebar`)
    property string fileUrl: ""
    property list<string> entries: []

    function isPinned(entry: string): bool {
        return root.entries.indexOf(entry) >= 0;
    }

    function save() {
        pinnedFile.setText(JSON.stringify(root.entries, null, 2));
    }

    function pin(entry: string) {
        if (root.isPinned(entry))
            return;
        root.entries = [entry].concat(root.entries);
        save();
    }

    function unpin(entry: string) {
        const next = root.entries.filter(item => item !== entry);
        if (next.length === root.entries.length)
            return;
        root.entries = next;
        save();
    }

    function toggle(entry: string) {
        if (root.isPinned(entry))
            root.unpin(entry);
        else
            root.pin(entry);
    }

    function refresh() {
        pinnedFile.reload();
    }

    Component.onCompleted: {
        mkdirProc.running = true;
    }

    Process {
        id: mkdirProc
        command: ["mkdir", "-p", root.stateDir]
        onExited: {
            root.fileUrl = `file://${root.stateDir}/pinned-clipboard.json`;
            root.refresh();
        }
    }

    FileView {
        id: pinnedFile
        path: root.fileUrl
        printErrors: false
        watchChanges: true
        onFileChanged: this.reload()
        onLoaded: {
            if (root.fileUrl.length === 0)
                return;
            try {
                const parsed = JSON.parse(pinnedFile.text() || "[]");
                root.entries = parsed.filter(item => typeof item === "string");
            } catch (e) {
                root.entries = [];
                root.save();
            }
        }
        onLoadFailed: (error) => {
            if (root.fileUrl.length === 0)
                return;
            root.entries = [];
            root.save();
        }
    }
}
```

### `/home/rdp/.config/quickshell/ii/services/Speaking.qml`

```qml
pragma Singleton
pragma ComponentBehavior: Bound

import qs.modules.common
import qs.modules.common.functions
import qs.services
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    property string stateDir: FileUtils.trimFileProtocol(`${Directories.state}/quickshell-speaking`)
    property string scriptDir: FileUtils.trimFileProtocol(Quickshell.shellPath("scripts/speaking"))
    property string mode: "idle" // idle, recording, paused, postprocessing, done, failed
    property string statusText: "Ready"
    property string sessionDir: ""
    property string transcriptPath: ""
    property string rawTranscriptPath: ""
    property string transcript: ""
    property string rawTranscript: ""
    property list<var> historyEntries: []
    property string selectedSourceName: ""
    property string cleanupMode: "groq"
    property bool storageReady: false
    property string recordStartedAt: ""
    property real elapsedSeconds: 0

    readonly property bool canStart: mode === "idle" || mode === "done" || mode === "failed"
    readonly property bool canPause: mode === "recording"
    readonly property bool canResume: mode === "paused"
    readonly property bool canStop: mode === "recording" || mode === "paused"
    readonly property bool controlsLocked: mode === "postprocessing"
    readonly property bool isActive: mode === "recording" || mode === "paused" || mode === "postprocessing"
    readonly property list<var> inputDevices: Audio.inputDevices
    readonly property string selectedSourceLabel: sourceLabelByName(selectedSourceName)
    readonly property string formattedElapsed: formatElapsed(elapsedSeconds)

    function shellQuote(text): string {
        return StringUtils.shellSingleQuoteEscape(text);
    }

    function formatElapsed(seconds): string {
        const total = Math.max(0, Math.floor(seconds));
        const mins = Math.floor(total / 60);
        const secs = total % 60;
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    }

    function sourceLabelByName(name: string): string {
        for (const node of root.inputDevices) {
            if (node && node.name === name)
                return Audio.friendlyDeviceName(node);
        }
        if (Audio.source)
            return Audio.friendlyDeviceName(Audio.source);
        return "Input device";
    }

    function selectInputDeviceByName(name: string) {
        if (!name || name.length === 0)
            return;
        for (const node of root.inputDevices) {
            if (node && node.name === name) {
                Audio.setDefaultSource(node);
                root.selectedSourceName = name;
                saveSettings();
                root.statusText = `Mic: ${Audio.friendlyDeviceName(node)}`;
                return;
            }
        }
    }

    function saveSettings() {
        const payload = {
            selectedSourceName: root.selectedSourceName,
            cleanupMode: root.cleanupMode
        };
        settingsFile.setText(JSON.stringify(payload, null, 2));
    }

    function setCleanupMode(modeName: string) {
        root.cleanupMode = modeName === "raw" ? "raw" : "groq";
        root.saveSettings();
    }

    function resetTranscriptFields() {
        root.transcript = "";
        root.rawTranscript = "";
        root.elapsedSeconds = 0;
    }

    function start() {
        if (!root.storageReady || !root.canStart || root.controlsLocked)
            return;
        const sessionName = Qt.formatDateTime(new Date(), "yyyyMMdd-hhmmss");
        root.sessionDir = `${root.stateDir}/${sessionName}`;
        root.transcriptPath = `${root.sessionDir}/transcript.txt`;
        root.rawTranscriptPath = `${root.sessionDir}/raw-transcript.txt`;
        root.resetTranscriptFields();
        root.recordStartedAt = new Date().toISOString();
        transcriptFile.path = `file://${root.transcriptPath}`;
        rawTranscriptFile.path = `file://${root.rawTranscriptPath}`;
        root.mode = "recording";
        root.statusText = "Recording";
        elapsedTimer.restart();
        recordProc.command = ["bash", "-lc", `SPEAKING_CLEANUP_MODE='${shellQuote(root.cleanupMode)}' '${shellQuote(root.scriptDir)}/record-session.sh' run '${shellQuote(root.sessionDir)}'`];
        recordProc.running = true;
    }

    function pause() {
        if (!root.canPause || root.controlsLocked)
            return;
        Quickshell.execDetached(["bash", "-lc", `touch '${shellQuote(root.sessionDir)}/pause'`]);
        root.mode = "paused";
        root.statusText = "Paused";
        elapsedTimer.stop();
    }

    function resume() {
        if (!root.canResume || root.controlsLocked)
            return;
        Quickshell.execDetached(["bash", "-lc", `rm -f '${shellQuote(root.sessionDir)}/pause'`]);
        root.mode = "recording";
        root.statusText = "Recording";
        elapsedTimer.restart();
    }

    function stop() {
        if (!root.canStop || root.controlsLocked)
            return;
        Quickshell.execDetached(["bash", "-lc", `rm -f '${shellQuote(root.sessionDir)}/pause'; touch '${shellQuote(root.sessionDir)}/stop'`]);
        root.mode = "postprocessing";
        root.statusText = "Transcribing";
        elapsedTimer.stop();
    }

    function transcribeFile(path) {
        const sessionName = `sample-${Qt.formatDateTime(new Date(), "yyyyMMdd-hhmmss")}`;
        root.sessionDir = `${root.stateDir}/${sessionName}`;
        root.transcriptPath = `${root.sessionDir}/transcript.txt`;
        root.rawTranscriptPath = `${root.sessionDir}/raw-transcript.txt`;
        root.resetTranscriptFields();
        transcriptFile.path = `file://${root.transcriptPath}`;
        rawTranscriptFile.path = `file://${root.rawTranscriptPath}`;
        root.mode = "postprocessing";
        root.statusText = "Transcribing sample";
        sampleProc.command = ["bash", "-lc", `SPEAKING_CLEANUP_MODE='${shellQuote(root.cleanupMode)}' '${shellQuote(root.scriptDir)}/record-session.sh' sample '${shellQuote(path)}' '${shellQuote(root.sessionDir)}'`];
        sampleProc.running = true;
    }

    function copyTranscript() {
        if (root.transcript.length === 0)
            return;
        Quickshell.execDetached(["bash", "-lc", `printf '%s' '${shellQuote(root.transcript)}' | wl-copy`]);
        root.statusText = "Copied transcript";
    }

    function setTranscript(text: string) {
        root.transcript = text;
    }

    function reloadOutputs() {
        transcriptFile.reload();
        rawTranscriptFile.reload();
        root.reloadHistory();
    }

    function reloadHistory() {
        if (root.storageReady)
            historyFile.reload();
    }

    function maybeApplySavedSource() {
        if (root.selectedSourceName.length > 0)
            root.selectInputDeviceByName(root.selectedSourceName);
    }

    Component.onCompleted: {
        initStorageProc.running = true;
    }

    Process {
        id: initStorageProc
        command: ["bash", "-lc", `mkdir -p '${root.shellQuote(root.stateDir)}'; touch '${root.shellQuote(root.stateDir)}/settings.json'; test -s '${root.shellQuote(root.stateDir)}/settings.json' || printf '{}\\n' > '${root.shellQuote(root.stateDir)}/settings.json'; touch '${root.shellQuote(root.stateDir)}/history.json'; test -s '${root.shellQuote(root.stateDir)}/history.json' || printf '[]\\n' > '${root.shellQuote(root.stateDir)}/history.json'`]
        onExited: (exitCode, exitStatus) => {
            root.storageReady = exitCode === 0;
            settingsFile.path = `file://${root.stateDir}/settings.json`;
            historyFile.path = `file://${root.stateDir}/history.json`;
            settingsFile.reload();
            historyFile.reload();
        }
    }

    Process {
        id: recordProc
        onExited: (exitCode, exitStatus) => {
            root.reloadOutputs();
            root.mode = exitCode === 0 ? "done" : "failed";
            root.statusText = exitCode === 0 ? "Done" : "Recording failed";
            elapsedTimer.stop();
        }
    }

    Process {
        id: sampleProc
        onExited: (exitCode, exitStatus) => {
            root.reloadOutputs();
            root.mode = exitCode === 0 ? "done" : "failed";
            root.statusText = exitCode === 0 ? "Sample done" : "Sample failed";
            elapsedTimer.stop();
        }
    }

    Timer {
        id: elapsedTimer
        interval: 1000
        repeat: true
        onTriggered: root.elapsedSeconds += 1
    }

    FileView {
        id: transcriptFile
        printErrors: false
        watchChanges: false
        onLoaded: root.transcript = transcriptFile.text().trim()
    }

    FileView {
        id: rawTranscriptFile
        printErrors: false
        watchChanges: false
        onLoaded: root.rawTranscript = rawTranscriptFile.text().trim()
    }

    FileView {
        id: historyFile
        printErrors: false
        watchChanges: true
        onFileChanged: this.reload()
        onLoaded: {
            try {
                const parsed = JSON.parse(historyFile.text() || "[]");
                root.historyEntries = Array.isArray(parsed) ? parsed : [];
            } catch (e) {
                root.historyEntries = [];
            }
        }
        onLoadFailed: (error) => {
            root.historyEntries = [];
            this.setText("[]\n");
        }
    }

    FileView {
        id: settingsFile
        printErrors: false
        watchChanges: true
        onFileChanged: this.reload()
        onLoaded: {
            try {
                const parsed = JSON.parse(settingsFile.text() || "{}");
                root.selectedSourceName = typeof parsed.selectedSourceName === "string" ? parsed.selectedSourceName : "";
                root.cleanupMode = parsed.cleanupMode === "raw" ? "raw" : "groq";
            } catch (e) {
                root.selectedSourceName = "";
                root.cleanupMode = "groq";
                this.setText("{}\n");
            }
            root.maybeApplySavedSource();
        }
        onLoadFailed: (error) => {
            root.selectedSourceName = "";
            root.cleanupMode = "groq";
            this.setText("{}\n");
        }
    }

    IpcHandler {
        target: "speaking"

        function transcribeSample(path: string): void {
            root.transcribeFile(path);
        }
    }
}
```

### `/home/rdp/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

base_dir="${XDG_DATA_HOME:-$HOME/.local/share}/quickshell-speaking"
src_dir="$base_dir/whisper.cpp"
model_dir="$base_dir/models"
model_path="$model_dir/ggml-small.en.bin"
model_url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin"

find_whisper_bin() {
    for candidate in \
        "${WHISPER_CPP_BIN:-}" \
        "$src_dir/build/bin/whisper-cli" \
        "$src_dir/build/bin/main" \
        "$src_dir/main" \
        "$(command -v whisper-cli 2>/dev/null || true)" \
        "$(command -v whisper.cpp 2>/dev/null || true)"; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

build_whisper_cpp() {
    mkdir -p "$base_dir"
    if [[ ! -d "$src_dir/.git" ]]; then
        git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$src_dir"
    fi
    cmake -S "$src_dir" -B "$src_dir/build" -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON
    cmake --build "$src_dir/build" -j"$(nproc)"
}

ensure_model() {
    mkdir -p "$model_dir"
    find "$model_dir" -maxdepth 1 -type f -name 'ggml-*.bin' ! -name 'ggml-small.en.bin' -delete
    if [[ ! -s "$model_path" ]]; then
        curl -L --fail --retry 3 -o "$model_path.tmp" "$model_url"
        mv "$model_path.tmp" "$model_path"
    fi
}

if ! bin="$(find_whisper_bin)"; then
    build_whisper_cpp
    bin="$(find_whisper_bin)"
fi

ensure_model

case "${1:-}" in
    --bin)
        printf '%s\n' "$bin"
        ;;
    --model)
        printf '%s\n' "$model_path"
        ;;
    *)
        printf 'WHISPER_BIN=%q\n' "$bin"
        printf 'WHISPER_MODEL=%q\n' "$model_path"
        ;;
esac
```

### `/home/rdp/.config/quickshell/ii/scripts/speaking/transcribe.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: transcribe.sh <audio-file>" >&2
    exit 2
fi

input_file="$1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ensure_script="$script_dir/ensure-whisper.sh"

WHISPER_BIN="$("$ensure_script" --bin)"
WHISPER_MODEL="$("$ensure_script" --model)"

work_dir="$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/quickshell-speaking.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

wav_file="$work_dir/input.wav"
out_base="$work_dir/transcript"

ffmpeg -hide_banner -loglevel error -y -i "$input_file" -ar 16000 -ac 1 -c:a pcm_s16le "$wav_file"

"$WHISPER_BIN" -m "$WHISPER_MODEL" -f "$wav_file" -l en -nt -otxt -of "$out_base" >/dev/null 2>/dev/null

if [[ -s "$out_base.txt" ]]; then
    sed 's/[[:space:]]\+$//' "$out_base.txt"
fi
```

### `/home/rdp/.config/quickshell/ii/scripts/speaking/record-session.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "usage: record-session.sh run <session-dir> | sample <audio-file> <session-dir>" >&2
    exit 2
fi

mode="$1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
transcribe_script="$script_dir/transcribe.sh"
cleanup_script="$script_dir/groq-cleanup.sh"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/quickshell-speaking"
history_file="$state_dir/history.json"
cleanup_mode="${SPEAKING_CLEANUP_MODE:-groq}"

ensure_history_file() {
    mkdir -p "$state_dir"
    if [[ ! -f "$history_file" ]]; then
        printf '[]\n' >"$history_file"
    fi
}

append_history() {
    local cleaned_text="$1"
    local raw_text="$2"
    ensure_history_file
    if ! command -v jq >/dev/null 2>&1; then
        return 0
    fi
    local ts tmp
    ts="$(date -Is)"
    tmp="$(mktemp)"
    jq --arg ts "$ts" --arg cleaned "$cleaned_text" --arg raw "$raw_text" '
        (if type == "array" then . else [] end) as $arr
        | [{timestamp: $ts, cleaned: $cleaned, raw: $raw}] + $arr
        | .[:250]
    ' "$history_file" >"$tmp" 2>/dev/null || {
        rm -f "$tmp"
        printf '[]\n' >"$history_file"
        return 0
    }
    mv "$tmp" "$history_file"
}

collect_raw_transcript() {
    local chunks_dir="$1"
    local raw_file="$2"
    : >"$raw_file"
    local chunk text
    shopt -s nullglob
    for chunk in "$chunks_dir"/chunk-*.wav; do
        text="$("$transcribe_script" "$chunk" || true)"
        text="$(printf '%s' "$text" | sed '/^[[:space:]]*$/d')"
        if [[ -n "$text" ]]; then
            printf '%s\n' "$text" >>"$raw_file"
        fi
    done
    shopt -u nullglob
}

finalize_transcript() {
    local raw_file="$1"
    local final_file="$2"
    local raw_text cleaned_text
    raw_text="$(cat "$raw_file" 2>/dev/null || true)"
    if [[ "$cleanup_mode" == "groq" && -n "${raw_text//[[:space:]]/}" ]]; then
        cleaned_text="$(printf '%s' "$raw_text" | "$cleanup_script" || true)"
    else
        cleaned_text="$raw_text"
    fi
    if [[ -z "${cleaned_text//[[:space:]]/}" ]]; then
        cleaned_text="$raw_text"
    fi
    printf '%s\n' "$cleaned_text" >"$final_file"
    append_history "$cleaned_text" "$raw_text"
}

if [[ "$mode" == "sample" ]]; then
    input_file="$2"
    session_dir="$3"
    mkdir -p "$session_dir"
    chunks_dir="$session_dir/chunks"
    mkdir -p "$chunks_dir"
    cp -f "$input_file" "$chunks_dir/chunk-00000.wav"
    raw_file="$session_dir/raw-transcript.txt"
    final_file="$session_dir/transcript.txt"
    collect_raw_transcript "$chunks_dir" "$raw_file"
    finalize_transcript "$raw_file" "$final_file"
    exit 0
fi

if [[ "$mode" != "run" ]]; then
    echo "unknown mode: $mode" >&2
    exit 2
fi

session_dir="$2"
mkdir -p "$session_dir/chunks"
: >"$session_dir/transcript.txt"
: >"$session_dir/raw-transcript.txt"
rm -f "$session_dir/stop" "$session_dir/pause"

index=0
while [[ ! -f "$session_dir/stop" ]]; do
    if [[ -f "$session_dir/pause" ]]; then
        sleep 0.3
        continue
    fi

    chunk_file="$session_dir/chunks/chunk-$(printf '%05d' "$index").wav"
    set +e
    timeout 4s pw-record --rate 16000 --channels 1 --format s16 "$chunk_file"
    record_code=$?
    set -e

    index=$((index + 1))

    if [[ $record_code -ne 0 && $record_code -ne 124 ]]; then
        exit "$record_code"
    fi
done

collect_raw_transcript "$session_dir/chunks" "$session_dir/raw-transcript.txt"
finalize_transcript "$session_dir/raw-transcript.txt" "$session_dir/transcript.txt"
```

### `/home/rdp/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

raw_text="$(cat)"
if [[ -z "${raw_text//[[:space:]]/}" ]]; then
    printf '%s\n' "$raw_text"
    exit 0
fi

groq_api_key="${GROQ_API_KEY:-}"
if [[ -z "$groq_api_key" ]]; then
    printf '%s\n' "$raw_text"
    exit 0
fi
endpoint='https://api.groq.com/openai/v1/chat/completions'
system_prompt='You are given a raw speech transcription.
Fix punctuation, capitalization, and spacing only.
Do NOT change wording, language, or meaning.
Keep Hindi/English mix exactly as spoken.

Return only the cleaned text.'

if ! command -v jq >/dev/null 2>&1; then
    printf '%s\n' "$raw_text"
    exit 0
fi

payload="$(jq -n \
    --arg model "llama-3.3-70b-versatile" \
    --arg system "$system_prompt" \
    --arg user "$raw_text" \
    '{
        model: $model,
        temperature: 0,
        messages: [
            { role: "system", content: $system },
            { role: "user", content: $user }
        ]
    }')"

response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

if ! curl -sS --fail "$endpoint" \
    -H "Authorization: Bearer ${groq_api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload" >"$response_file"; then
    printf '%s\n' "$raw_text"
    exit 0
fi

cleaned="$(jq -r '.choices[0].message.content // empty' "$response_file" 2>/dev/null || true)"
if [[ -z "${cleaned//[[:space:]]/}" ]]; then
    printf '%s\n' "$raw_text"
    exit 0
fi

printf '%s\n' "$cleaned"
```

### `/home/rdp/.config/hypr/hyprland/execs.conf`

```ini
# Bar, wallpaper
exec-once = ~/.config/hypr/hyprland/scripts/start_geoclue_agent.sh
exec-once = qs -c $qsConfig &
exec-once = ~/.config/hypr/custom/scripts/__restore_video_wallpaper.sh

# Core components (authentication, lock screen, notification daemon)
exec-once = gnome-keyring-daemon --start --components=secrets
exec-once = hypridle
exec-once = dbus-update-activation-environment --all
exec-once = sleep 1 && dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP # Some fix idk

# Audio
exec-once = easyeffects --hide-window --service-mode

# Clipboard: history
# exec-once = wl-paste --watch cliphist store &
exec-once = wl-paste --type text --watch bash -c 'cliphist store && qs -c $qsConfig ipc call cliphistService update'
exec-once = wl-paste --type image --watch bash -c 'cliphist store && qs -c $qsConfig ipc call cliphistService update'

# Cursor
exec-once = hyprctl setcursor Bibata-Modern-Classic 24

# Fix dock pinned apps not launching properly (https://github.com/end-4/dots-hyprland/issues/2200)
# This causes https://github.com/end-4/dots-hyprland/issues/2427
# exec-once = sleep 3.5 && hyprctl reload && sleep 0.5 && touch ~/.config/quickshell/ii/shell.qml
```

### `/home/rdp/.config/hypr/custom/execs.conf`

```ini
# hyprlang noerror false
# You can make apps auto-start here
# Relevant Hyprland wiki section: https://wiki.hyprland.org/Configuring/Keywords/#executing

# Input method
# exec-once = fcitx5
```

### `/home/rdp/.config/quickshell/ii/docs/whisper-local-usage.md`

```markdown
# Local Whisper (`small.en`) Usage Guide

This setup uses `whisper.cpp` locally with `ggml-small.en.bin` in English mode.

## Files

- Setup script: `~/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh`
- Transcribe script: `~/.config/quickshell/ii/scripts/speaking/transcribe.sh`
- Session script: `~/.config/quickshell/ii/scripts/speaking/record-session.sh`
- Groq cleanup script: `~/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh`
- Model directory: `~/.local/share/quickshell-speaking/models/`
- History file: `~/.local/state/quickshell-speaking/history.json`

## 1. Ensure Runtime And Model

```bash
~/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh
```

This builds or fetches `whisper.cpp` if needed and keeps only:

- `ggml-small.en.bin`

## 2. Transcribe One Audio File Locally

```bash
~/.config/quickshell/ii/scripts/speaking/transcribe.sh /path/to/audio-file.ogg
```

The script uses `ffmpeg` to convert the input to 16 kHz mono WAV before passing it to `whisper-cli`.

## 3. Use Clean Or Raw Session Mode

Clean mode uses local Whisper first, then Groq punctuation/capitalization cleanup:

```bash
SPEAKING_CLEANUP_MODE=groq ~/.config/quickshell/ii/scripts/speaking/record-session.sh sample /path/to/audio.ogg /tmp/speaking-clean
```

Raw mode uses local Whisper only and never calls Groq:

```bash
SPEAKING_CLEANUP_MODE=raw ~/.config/quickshell/ii/scripts/speaking/record-session.sh sample /path/to/audio.ogg /tmp/speaking-raw
```

Both modes write:

- Raw transcript: `<session-dir>/raw-transcript.txt`
- Final transcript: `<session-dir>/transcript.txt`
- History entry: `~/.local/state/quickshell-speaking/history.json`

## 4. Reuse In Other Projects

```bash
WHISPER_HELPER="$HOME/.config/quickshell/ii/scripts/speaking/transcribe.sh"
"$WHISPER_HELPER" ./sample.wav > transcript.txt
```

Optional cleanup:

```bash
cat transcript.txt | ~/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh > cleaned.txt
```

If the Groq API call fails, the cleanup script returns the raw text.
```

### `/home/rdp/.config/quickshell/ii/docs/left-sidebar-changes.md`

```markdown
# Left Sidebar Changes

## Current State

- The visible left sidebar no longer exposes AI, ActivityWatch, or the old tabwatch tracker.
- The sidebar is now a compact clipboard and speaking workflow.
- The panel width is `500px`.
- The left rail is icon-only:
  - Clipboard
  - Pinned
  - Images
  - Transcribed
- Rail labels are available as hover tooltips.

## Clipboard

- Clipboard entries still come from `cliphist`.
- The default Clipboard view shows non-image entries.
- Images are shown in the Images rail view.
- Pinned clips are stored in `~/.local/state/quickshell-sidebar/pinned-clipboard.json`.
- Clipboard display remains capped at 35 entries.
- Up/Down keyboard navigation keeps the selected row visible.
- The clipboard list is a direct `ListView`, so keyboard navigation can reliably call `positionViewAtIndex`.
- Click or Enter pastes into the focused app and closes the sidebar.
- Delete still happens only through the explicit delete button.
- Hovering a clipboard row shows a full-message preview tooltip.

## Speaking

- The bottom section is the speaking/transcription panel.
- Recording writes short chunks while recording and transcribes after Stop.
- Current state flow:
  - `idle`
  - `recording`
  - `paused`
  - `postprocessing`
  - `done`
  - `failed`
- Recording shows a neutral pulse animation and elapsed timer.
- Postprocessing shows a neutral loader/spinner.
- The transcript field is editable and scrollable.
- The mic selector uses `Audio.inputDevices` and `Audio.setDefaultSource(node)`.
- The chosen mic is persisted in `~/.local/state/quickshell-speaking/settings.json`.

## Cleanup Mode

- `Clean` mode is selected by default.
- `Clean` uses local Whisper first, then Groq punctuation/capitalization cleanup.
- `Raw` uses local Whisper only and skips Groq entirely.
- The selected cleanup mode is persisted in `~/.local/state/quickshell-speaking/settings.json`.
- Script interface:
  - `SPEAKING_CLEANUP_MODE=groq`
  - `SPEAKING_CLEANUP_MODE=raw`

## Whisper

- The only accepted model is `ggml-small.en.bin`.
- Model directory:
  - `~/.local/share/quickshell-speaking/models/`
- Old `base` model files were removed by `ensure-whisper.sh`.
- `transcribe.sh` runs local `whisper-cli` with English mode.

## Transcribed History

- Transcription history is stored in:
  - `~/.local/state/quickshell-speaking/history.json`
- `Speaking.qml` now creates and loads the history file deterministically.
- `Speaking.reloadHistory()` refreshes history after a session finishes.
- The Transcribed rail view binds to refreshed `Speaking.historyEntries`.

## Removed Tracker Work

- Removed active ActivityWatch/tabwatch UI and services.
- Removed old tabwatch autostart lines from Hypr configs.
- Removed old tabwatch runtime state:
  - `~/.local/state/quickshell-tabwatch/`

## Important Files

- `~/.config/quickshell/ii/modules/ii/sidebarLeft/SidebarLeft.qml`
- `~/.config/quickshell/ii/modules/ii/sidebarLeft/SidebarLeftContent.qml`
- `~/.config/quickshell/ii/services/Speaking.qml`
- `~/.config/quickshell/ii/services/PinnedClipboard.qml`
- `~/.config/quickshell/ii/scripts/speaking/ensure-whisper.sh`
- `~/.config/quickshell/ii/scripts/speaking/transcribe.sh`
- `~/.config/quickshell/ii/scripts/speaking/record-session.sh`
- `~/.config/quickshell/ii/scripts/speaking/groq-cleanup.sh`
- `~/.config/quickshell/ii/docs/whisper-local-usage.md`
- `~/.config/quickshell/ii/docs/left-sidebar-full-audit-2026-05-05.md`

## Latest Verification

- `bash -n quickshell/ii/scripts/speaking/record-session.sh` passed.
- `timeout 7s qs -c ii` reached `Configuration Loaded`.
- Existing unrelated warnings remained for notification registration, missing `C.json`, polkit listener duplication, and an existing Revealer binding loop.
- Raw sample mode created matching raw/final transcript output and appended history.
- Clean sample mode called the Groq cleanup path and appended history.
- Existing history file contains entries and is available at shell startup:
  - `~/.local/state/quickshell-speaking/history.json`

## Backups

- Latest backup from this polish pass:
  - `~/.config/.codex-backups/sidebar-polish-20260505-101248/`
```
