#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

alias ls='ls --color=auto'
alias grep='grep --color=auto'
PS1='[\u@\h \W]\$ '
eval "$(starship init bash)"




# Auto-center Fastfetch and pick a random bunny
fastfetch() {
    local random_bunny=$(find ~/.config/fastfetch/bunnies -name "*.txt" -size +0c 2>/dev/null | shuf -n 1)
    [ -n "$random_bunny" ] && cp "$random_bunny" ~/.config/fastfetch/bunny.txt

    local logo_lines=$(wc -l < ~/.config/fastfetch/bunny.txt 2>/dev/null || echo 15)
    local text_lines=15
    if [ "$logo_lines" -gt "$text_lines" ]; then
        local pad=$(( (logo_lines - text_lines) / 2 ))
        local breaks=$(printf '"break",%.0s' $(seq 1 $pad))
        sed "s/\"title\",/$breaks\"title\",/" ~/.config/fastfetch/config.jsonc > /tmp/fastfetch-centered.jsonc
        command fastfetch --logo-padding-top 0 -c /tmp/fastfetch-centered.jsonc "$@"
    else
        local pad=$(( (text_lines - logo_lines) / 2 ))
        command fastfetch --logo-padding-top "$pad" "$@"
    fi
}

# Marshmellow Lava Lamp & Weather Shortcuts
alias lava='lavat -c magenta -k cyan -R 2'
weather() {
    if [ "$1" = "full" ]; then
        curl -s "wttr.in/$2"
    else
        curl -s "wttr.in/$1?0"
    fi
}

# Emergency 1-word restore for Hyprland config
alias fixhypr='cp ~/.config/hypr/hyprland.lua.safe ~/.config/hypr/hyprland.lua.tmp && mv ~/.config/hypr/hyprland.lua.tmp ~/.config/hypr/hyprland.lua && hyprctl reload && echo "🌸 Hyprland restored to safety!"'

# 1-word command to sync and push all Marshmellow dotfiles to GitHub
alias backupdots='cp ~/.config/hypr/hyprland.lua ~/.config/hypr/hyprland.lua.safe && ~/marshmellow-dotfiles/sync.sh && cd ~/marshmellow-dotfiles && git add . && git commit -m "Update Marshmellow dotfiles 🌸" && git push && cd - >/dev/null'


# Custom update command: runs Timeshift, then pacman
update() {
    echo "--> [Timeshift] Creating pre-update snapshot..."
    sudo timeshift --create --comments "Auto-backup before update"
    
    if [ $? -eq 0 ]; then
        echo "--> [Timeshift] Snapshot successful! Proceeding with update..."
        sudo pacman -Syu
    else
        echo "--> [Timeshift] Error: Snapshot failed! Aborting update for safety."
        return 1
    fi
}
