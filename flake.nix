{
  description = "The build environment of the book BCW-2 Soubou";

  # One release of nixpkgs pins every tool: nixos-26.05, git revision
  # c508844df6c28fa6dabc1b6af70f3ccbd65c5201. flake.lock records the hash of
  # its tarball. To move to another release, change the URL and run
  # nix flake update.
  inputs.nixpkgs.url = "https://releases.nixos.org/nixos/26.05/nixos-26.05.10529.c508844df6c2/nixexprs.tar.xz";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      shell = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        pkgs.mkShellNoCC {
          packages = [
            (pkgs.python3.withPackages (ps: [ ps.sphinx ps.z3-solver ]))
            pkgs.verilator
            pkgs.iverilog
            # For make weave: latexmk, the LaTeX packages that the LaTeX of Sphinx
            # loads, and the fonts that tools/weave.py sets (Times, Helvetica and
            # Courier).
            (pkgs.texliveSmall.withPackages (ps: [
              ps.latexmk
              ps.capt-of
              ps.framed
              ps.needspace
              ps.tabulary
              ps.titlesec
              ps.varwidth
              ps.wrapfig
              ps.times
              ps.helvetic
              ps.courier
              ps.rsfs
            ]))
            pkgs.gnumake
            pkgs.git
            pkgs.bash
          ];
          # The Makefile stops outside this environment.
          BCW_ENV = "1";
        };
    in
    {
      devShells = nixpkgs.lib.genAttrs systems (system: { default = shell system; });
    };
}
