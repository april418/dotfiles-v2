// goda-pm.vim の設定。make_state のたびに goda-pm がこのモジュールをビルドして走らせる。
package main

import (
	"context"

	"github.com/Shougo/goda-pm-ext/ext/installer"
	"github.com/Shougo/goda-pm-ext/ext/protocol/git"
	"github.com/Shougo/goda-pm-ext/ext/toml"
	"github.com/Shougo/goda-pm.vim/pm"
)

const pluginsToml = "~/.vim/goda-pm/plugins.toml"

func main() {
	b := pm.New()
	b.AddProtocol(git.New())
	b.AddExt(installer.New())
	b.SetConfig(config)
	b.Main()
}

func config(ctx context.Context, c *pm.ConfigArgs) (*pm.ConfigReturn, error) {
	c.Options.Protocols = []string{"git"}

	t, err := toml.Load(ctx, c.Host, pluginsToml, pm.Plugin{"lazy": false})
	if err != nil {
		return nil, err
	}

	// main.go 自身は goda-pm が見るので、ここでは TOML だけを足す。
	checkFile, err := c.Expand(ctx, pluginsToml)
	if err != nil {
		return nil, err
	}

	return &pm.ConfigReturn{
		CheckFiles: []string{checkFile},
		Ftplugins:  t.Ftplugins,
		Plugins:    t.Plugins,
	}, nil
}
