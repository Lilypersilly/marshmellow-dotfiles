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
