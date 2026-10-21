#!/usr/bin/env bash
DOTS="$HOME/marshmellow-dotfiles"

# 1. Copy all .config folders we customized
for dir in hypr waybar wofi kitty swaync swayosd wlogout fastfetch gtk-3.0 gtk-4.0 qt6ct fontconfig; do
    [ -d "$HOME/.config/$dir" ] && cp -r "$HOME/.config/$dir" "$DOTS/.config/"
done

# 2. Copy single config files
for file in starship.toml kdeglobals kwriterc katerc; do
    [ -f "$HOME/.config/$file" ] && cp "$HOME/.config/$file" "$DOTS/.config/"
done
cp "$HOME/.bashrc" "$DOTS/.bashrc"

# 3. Copy custom .local/share files (Help desktop entry, Marshmellow colors, KWrite theme)
cp "$HOME/.local/share/applications/hypr-help.desktop" "$DOTS/.local/share/applications/" 2>/dev/null
cp "$HOME/.local/share/color-schemes/Marshmellow.colors" "$DOTS/.local/share/color-schemes/" 2>/dev/null
cp "$HOME/.local/share/org.kde.syntax-highlighting/themes/Marshmellow.theme" "$DOTS/.local/share/org.kde.syntax-highlighting/themes/" 2>/dev/null

echo "🌸 All Marshmellow dotfiles synced to $DOTS!"
