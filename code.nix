{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    nodejs
    nodePackages.pnpm
  ];

  shellHook = ''
    echo "Setting up Code environment with PNPM..."
    
    # Create a temporary directory for the package
    TEMP_DIR=$(mktemp -d)
    cd $TEMP_DIR
    
    # Initialize PNPM workspace
    echo "Initializing PNPM workspace..."
    pnpm init > /dev/null 2>&1
    
    # Install the latest Claude Code with PNPM
    echo "Installing @latest using PNPM..."
    pnpm add @anthropic-ai/claude-code@latest
    pnpm install @anthropic-ai/claude-code

    # Add PNPM bin directory to PATH
    export PATH="$TEMP_DIR/node_modules/.bin:$PATH"
    
    echo "Install successful!"
    
    # Return to the original directory
    cd - > /dev/null
    
    # Clean up function when exiting the shell
    cleanup() {
      echo "Cleaning up temporary files..."
      rm -rf $TEMP_DIR
    }
    trap cleanup EXIT
  '';
}
