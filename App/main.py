# Entry point: no arguments opens the GUI, any arguments run the command line (see --help).
# Kept in syntax any Python can parse, so an old Python shows the version message instead of a SyntaxError.
import SystemSupport

SystemSupport.requireSupportedPython()

if __name__ == "__main__":
    import CommandLine
    CommandLine.main()
