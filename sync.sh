#!/usr/bin/env bash
DOTS="$HOME/marshmellow-dotfiles"

mkdir -p "$DOTS/.config/btop/themes"
mkdir -p "$DOTS/.config/vesktop/themes"
mkdir -p "$DOTS/.config/vesktop/settings"
mkdir -p "$DOTS/.local/share/applications"
mkdir -p "$DOTS/.local/share/color-schemes"
mkdir -p "$DOTS/.local/share/org.kde.syntax-highlighting/themes"

# 1. Copy full .config folders we customized
for dir in hypr waybar wofi kitty swaync swayosd wlogout fastfetch gtk-3.0 gtk-4.0 qt6ct fontconfig cava waypaper; do
    [ -d "$HOME/.config/$dir" ] && cp -r "$HOME/.config/$dir" "$DOTS/.config/"
done

# 2. Copy btop & Vesktop themes/settings (skipping private Discord login tokens!)
cp -r "$HOME/.config/btop/themes/"* "$DOTS/.config/btop/themes/" 2>/dev/null
cp "$HOME/.config/btop/btop.conf" "$DOTS/.config/btop/" 2>/dev/null
cp -r "$HOME/.config/vesktop/themes/"* "$DOTS/.config/vesktop/themes/" 2>/dev/null
cp -r "$HOME/.config/vesktop/settings/"* "$DOTS/.config/vesktop/settings/" 2>/dev/null

# 3. Copy standalone config files & YouTube Music CSS
for file in starship.toml kdeglobals kwriterc katerc marshmellow-ytm.css; do
    [ -f "$HOME/.config/$file" ] && cp "$HOME/.config/$file" "$DOTS/.config/"
done
cp "$HOME/.bashrc" "$DOTS/.bashrc"

# 4. Copy custom .local/share desktop entries & themes
for app in hypr-help.desktop marshmellow-studio.desktop marshmellow-wallpapers.desktop; do
    [ -f "$HOME/.local/share/applications/$app" ] && cp "$HOME/.local/share/applications/$app" "$DOTS/.local/share/applications/"
done
cp "$HOME/.local/share/color-schemes/Marshmellow.colors" "$DOTS/.local/share/color-schemes/" 2>/dev/null
cp "$HOME/.local/share/org.kde.syntax-highlighting/themes/Marshmellow.theme" "$DOTS/.local/share/org.kde.syntax-highlighting/themes/" 2>/dev/null

echo "🌸 All Day 1 & Day 2 Marshmellow dotfiles synced to $DOTS!"
