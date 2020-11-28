from ConfigParser import ConfigParser
import re

class MyConfigParser(ConfigParser):
    def set(self, section, option, value=None, end=None):
        if end != None:
            option = option + end
        ConfigParser.set(self, section, option, value)

    def write(self, fp):
        if self._defaults:
            fp.write("[%s]\n" % DEFAULTSECT)
            for (key, value) in self._defaults.items():
                if key.endswith('_r_'):
                    sepstr=' '
                elif key.endswith('_e_'):
                    sepstr='='
                else:
                    sepstr=' = '
                key = re.split('_r_|_e_', key)[0]
                fp.write("%s%s%s\n" % (key, str(value).replace('\n', sepstr, '\n\t')))
            fp.write("\n")
        for section in self._sections:
            fp.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key == "__name__":
                    continue
                if key.endswith('_r_'):
                    sepstr=' '
                elif key.endswith('_e_'):
                    sepstr='='
                else:
                    sepstr=' = '
                key = re.split('_r_|_e_', key)[0]
                if (value is not None) or (self._optcre == self.OPTCRE):
                    key = sepstr.join((key, str(value).replace('\n', '\n\t')))
                fp.write("%s\n" % (key))
            fp.write("\n")

