;;; Directory Local Variables            -*- no-byte-compile: t -*-
;;; For more information see (info "(emacs) Directory Variables")

((nil . ((projectile-project-type . python-uv)
         (projectile-tasks . (("format" . "uv run ruff format")))
         (python-shell-interpreter-args . "-i")
         (python-shell-interpreter . ".venv/bin/python")))
 (python-mode . ((python-pytest-executable . "uv run pytest"))))
