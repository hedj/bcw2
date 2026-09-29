{
  description = "The build environment of the book BCW-2 Soubou";

  # One release of nixpkgs pins every tool: nixpkgs-unstable 26.11pre1080803,
  # git revision 419fe0f449b3fbe3bdd53d9840288db4509ec32e. flake.lock records
  # the hash of its tarball. To move to another release, change the URL and
  # run nix flake update.
  inputs.nixpkgs.url = "https://releases.nixos.org/nixpkgs/nixpkgs-26.11pre1080803.419fe0f449b3/nixexprs.tar.xz";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      shell = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        # mkShell, not mkShellNoCC, so that the C compiler of nixpkgs builds the C
        # models and the C++ of Verilator, and not the compiler of the host.
        pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: [ ps.sphinx ps.z3-solver ps.pytest ps.pytest-xdist ps.radon ps.textstat ]))
            pkgs.verilator
            # Verilator compiles the same runtime and much the same C++ for each test,
            # so ccache keeps each object and reuses it (see OBJCACHE below).
            pkgs.ccache
            pkgs.iverilog
            # The formal tools: yosys writes a module as SMT for z3, and SymbiYosys
            # proves properties with the solver Yices.
            pkgs.yosys
            pkgs.sby
            pkgs.yices
            # The FPGA tools for the ECP5: nextpnr places and routes, and ecppack of
            # trellis writes the bitstream.
            pkgs.nextpnr
            pkgs.trellis
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
          # The Makefile stops outside this environment. BCW_ENV is the hash of the two
          # files that fix it, so ./dev inside it runs a command at once when they match.
          BCW_ENV = builtins.hashString "sha256" (builtins.readFile ./flake.nix + builtins.readFile ./flake.lock);
          # The makefiles that Verilator writes run each compile through OBJCACHE.
          # ccache keys each object on the compiler and the preprocessed source, so
          # a hit gives the same object as a compile. The cache is ~/.cache/ccache.
          OBJCACHE = "ccache";
          # textstat counts English syllables with the CMU dictionary of NLTK. This
          # pins the dictionary, so that textstat does not download it at run time.
          NLTK_DATA = "${pkgs.nltk-data.cmudict}";
        };
    in
    {
      devShells = nixpkgs.lib.genAttrs systems (system: { default = shell system; });
    };
}
