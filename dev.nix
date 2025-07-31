{
  pkgs ? import <nixpkgs> {},
}:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311Full
    pkgs.python311Packages.pip
    pkgs.python311Packages.setuptools
    pkgs.uvicorn
  ];

  shellHook = ''
    echo "✅ Using Python: $(python3.11 --version)"
    if [ ! -d ".venv" ]; then
      python3.11 -m venv .venv
    fi
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
  '';
}
