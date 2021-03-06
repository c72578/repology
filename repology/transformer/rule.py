# Copyright (C) 2018 Dmitry Marakasov <amdmi3@amdmi3.ru>
#
# This file is part of repology
#
# repology is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# repology is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with repology.  If not, see <http://www.gnu.org/licenses/>.

import pprint
import re
import sys

from libversion import version_compare

from repology.package import PackageFlags


DOLLAR0 = re.compile('\$0', re.ASCII)
DOLLARN = re.compile('\$([0-9])', re.ASCII)


class PackageContext:
    __slots__ = ['flags', 'rulesets']

    def __init__(self):
        self.flags = set()
        self.rulesets = set()

    def add_flag(self, name):
        self.flags.add(name)

    def has_flag(self, name):
        return name in self.flags

    def has_flags(self, names):
        return not self.flags.isdisjoint(names)

    def has_rulesets(self, rulesets):
        return not self.rulesets.isdisjoint(rulesets)

    def set_rulesets(self, rulesets):
        self.rulesets = set(rulesets)


class MatchContext:
    __slots__ = ['name_match', 'ver_match', 'last']

    def __init__(self):
        self.name_match = None
        self.ver_match = None
        self.last = False


class Rule:
    __slots__ = ['data', 'matchers', 'actions', 'names', 'namepat', 'matches', 'number', 'pretty']

    def __init__(self, number, ruledata):
        self.names = None
        self.namepat = None
        self.number = number
        self.matches = 0

        self.pretty = pprint.PrettyPrinter(width=10000).pformat(ruledata)

        self.matchers = []
        self.actions = []

        def as_list(val):
            return val if isinstance(val, list) or isinstance(val, set) else [val]

        def as_lowercase_list(val):
            return [v.lower() for v in as_list(val)]

        def as_set(val):
            return set(as_list(val))

        def as_lowercase_set(val):
            return set(as_lowercase_list(val))

        # These conditional blocks use local variables which are then captured by
        # nested functions. MAKE SURE that names for all these are unique, because
        # they are common to the whole function, and reusing the name for multiple
        # conditions or actions will break formerly defined ones

        # matchers
        if 'ruleset' in ruledata:
            rulesets = as_set(ruledata['ruleset'])

            def matcher(package, package_context, match_context):
                return package_context.has_rulesets(rulesets)

            self.matchers.append(matcher)

        if 'noruleset' in ruledata:
            norulesets = as_set(ruledata['noruleset'])

            def matcher(package, package_context, match_context):
                return not package_context.has_rulesets(norulesets)

            self.matchers.append(matcher)

        if 'category' in ruledata:
            categories = as_lowercase_set(ruledata['category'])

            def matcher(package, package_context, match_context):
                return package.category and package.category.lower() in categories

            self.matchers.append(matcher)

        if 'name' in ruledata:
            names = as_list(ruledata['name'])

            if 'setname' in ruledata:
                names = [DOLLAR0.sub(ruledata['setname'], name) for name in names]

            self.names = names
            names = set(names)

            if len(names) == 1:
                name = names.pop()

                def matcher(package, package_context, match_context):
                    return package.effname == name

                self.matchers.append(matcher)
            else:
                def matcher(package, package_context, match_context):
                    return package.effname in names

                self.matchers.append(matcher)

        if 'namepat' in ruledata:
            namepat = ruledata['namepat'].replace('\n', '')

            if 'setname' in ruledata:
                namepat = DOLLAR0.sub(ruledata['setname'], namepat)

            self.namepat = namepat
            namepat = re.compile(namepat, re.ASCII)

            def matcher(package, package_context, match_context):
                match = namepat.fullmatch(package.effname)
                if match:
                    match_context.name_match = match
                    return True
                return False

            self.matchers.append(matcher)

        if 'ver' in ruledata:
            versions = as_set(ruledata['ver'])

            if len(versions) == 1:
                version = versions.pop()

                def matcher(package, package_context, match_context):
                    return package.version == version

                self.matchers.append(matcher)
            else:
                def matcher(package, package_context, match_context):
                    return package.version in versions

                self.matchers.append(matcher)

        if 'verpat' in ruledata:
            verpat = re.compile(ruledata['verpat'].replace('\n', '').lower(), re.ASCII)

            def matcher(package, package_context, match_context):
                match = verpat.fullmatch(package.version.lower())
                if match:
                    match_context.ver_match = match
                    return True
                return False

            self.matchers.append(matcher)

        if 'verlonger' in ruledata:
            verlonger = ruledata['verlonger']

            def matcher(package, package_context, match_context):
                return len(re.split('[^a-zA-Z0-9]', package.version)) > verlonger

            self.matchers.append(matcher)

        if 'vergt' in ruledata:
            vergt = ruledata['vergt']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, vergt) > 0

            self.matchers.append(matcher)

        if 'verge' in ruledata:
            verge = ruledata['verge']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, verge) >= 0

            self.matchers.append(matcher)

        if 'verlt' in ruledata:
            verlt = ruledata['verlt']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, verlt) < 0

            self.matchers.append(matcher)

        if 'verle' in ruledata:
            verle = ruledata['verle']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, verle) <= 0

            self.matchers.append(matcher)

        if 'vereq' in ruledata:
            vereq = ruledata['vereq']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, vereq) == 0

            self.matchers.append(matcher)

        if 'verne' in ruledata:
            verne = ruledata['verne']

            def matcher(package, package_context, match_context):
                return version_compare(package.version, verne) != 0

            self.matchers.append(matcher)

        if 'wwwpat' in ruledata:
            wwwpat = re.compile(ruledata['wwwpat'].replace('\n', '').lower(), re.ASCII)

            def matcher(package, package_context, match_context):
                return package.homepage and wwwpat.fullmatch(package.homepage)

            self.matchers.append(matcher)

        if 'wwwpart' in ruledata:
            wwwparts = as_lowercase_list(ruledata['wwwpart'])

            def matcher(package, package_context, match_context):
                if not package.homepage:
                    return False
                for wwwpart in wwwparts:
                    if wwwpart in package.homepage.lower():
                        return True
                return False

            self.matchers.append(matcher)

        if 'flag' in ruledata:
            flags = as_set(ruledata['flag'])

            def matcher(package, package_context, match_context):
                return package_context.has_flags(flags)

            self.matchers.append(matcher)

        if 'noflag' in ruledata:
            noflags = as_set(ruledata['noflag'])

            def matcher(package, package_context, match_context):
                return not package_context.has_flags(noflags)

            self.matchers.append(matcher)

        if 'is_p_is_patch' in ruledata:
            is_p_is_patch = ruledata['is_p_is_patch']

            def matcher(package, package_context, match_context):
                return package.HasFlag(PackageFlags.p_is_patch) == is_p_is_patch

            self.matchers.append(matcher)

        # actions
        if 'remove' in ruledata:
            remove_flag = ruledata['remove']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.remove, remove_flag)

            self.actions.append(action)

        if 'ignore' in ruledata:
            ignore_flag = ruledata['ignore']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.ignore, ignore_flag)

            self.actions.append(action)

        if 'weak_devel' in ruledata:
            weak_devel_flag = ruledata['weak_devel']

            def action(package, package_context, match_context):
                # XXX: currently sets ignore; change to set non-viral variant of devel (#654)
                package.SetFlag(PackageFlags.ignore, weak_devel_flag)

            self.actions.append(action)

        if 'devel' in ruledata:
            devel_flag = ruledata['devel']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.devel, devel_flag)

            self.actions.append(action)

        if 'p_is_patch' in ruledata:
            p_is_patch_flag = ruledata['p_is_patch']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.p_is_patch, p_is_patch_flag)

            self.actions.append(action)

        if 'any_is_patch' in ruledata:
            any_is_patch_flag = ruledata['any_is_patch']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.any_is_patch, any_is_patch_flag)

            self.actions.append(action)

        if 'outdated' in ruledata:
            outdated_flag = ruledata['outdated']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.outdated, outdated_flag)

            self.actions.append(action)

        if 'legacy' in ruledata:
            legacy_flag = ruledata['legacy']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.legacy, legacy_flag)

            self.actions.append(action)

        if 'incorrect' in ruledata:
            incorrect_flag = ruledata['incorrect']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.incorrect, incorrect_flag)

            self.actions.append(action)

        if 'untrusted' in ruledata:
            untrusted_flag = ruledata['untrusted']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.untrusted, untrusted_flag)

            self.actions.append(action)

        if 'noscheme' in ruledata:
            noscheme_flag = ruledata['noscheme']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.noscheme, noscheme_flag)

            self.actions.append(action)

        if 'rolling' in ruledata:
            rolling_flag = ruledata['rolling']

            def action(package, package_context, match_context):
                package.SetFlag(PackageFlags.rolling, rolling_flag)

            self.actions.append(action)

        if 'snapshot' in ruledata:
            snapshot_flag = ruledata['snapshot']

            def action(package, package_context, match_context):
                # XXX: the same as ignored for now
                package.SetFlag(PackageFlags.ignore, snapshot_flag)

            self.actions.append(action)

        if 'successor' in ruledata:
            successor_flag = ruledata['successor']

            def action(package, package_context, match_context):
                # XXX: the same as devel for now
                package.SetFlag(PackageFlags.devel, successor_flag)

            self.actions.append(action)

        if 'generated' in ruledata:
            generated_flag = ruledata['generated']

            def action(package, package_context, match_context):
                # XXX: the same as rolling for now
                package.SetFlag(PackageFlags.rolling, generated_flag)

            self.actions.append(action)

        if 'last' in ruledata:
            def action(package, package_context, match_context):
                match_context.last = True

            self.actions.append(action)

        if 'addflavor' in ruledata:
            want_flavors = None
            if isinstance(ruledata['addflavor'], str):
                want_flavors = [ruledata['addflavor']]
            elif isinstance(ruledata['addflavor'], list):
                want_flavors = ruledata['addflavor']
            elif not isinstance(ruledata['addflavor'], bool):
                raise RuntimeError('addflavor must be boolean or str or list')

            def action(package, package_context, match_context):
                flavors = want_flavors if want_flavors else [package.effname]

                if match_context.name_match:
                    flavors = [DOLLARN.sub(lambda x: match_context.name_match.group(int(x.group(1))), flavor) for flavor in flavors]
                else:
                    flavors = [DOLLAR0.sub(package.effname, flavor) for flavor in flavors]

                flavors = [flavor.strip('-') for flavor in flavors]

                package.flavors += [flavor for flavor in flavors if flavor]

            self.actions.append(action)

        if 'resetflavors' in ruledata:
            def action(package, package_context, match_context):
                package.flavors = []

            self.actions.append(action)

        if 'addflag' in ruledata:
            addflags = as_list(ruledata['addflag'])

            def action(package, package_context, match_context):
                for flag in addflags:
                    package_context.add_flag(flag)

            self.actions.append(action)

        if 'setname' in ruledata:
            setname = ruledata['setname']

            def action(package, package_context, match_context):
                if match_context.name_match:
                    package.effname = DOLLARN.sub(lambda x: match_context.name_match.group(int(x.group(1))), setname)
                else:
                    package.effname = DOLLAR0.sub(package.effname, setname)

            self.actions.append(action)

        if 'setver' in ruledata:
            setver = ruledata['setver']

            def action(package, package_context, match_context):
                version_before_fix = package.version

                if package.origversion is None:
                    package.origversion = package.version

                if match_context.ver_match:
                    package.version = DOLLARN.sub(lambda x: match_context.ver_match.group(int(x.group(1))), setver)
                else:
                    package.version = DOLLAR0.sub(package.version, setver)

                package.verfixed = package.version != version_before_fix

            self.actions.append(action)

        if 'replaceinname' in ruledata:
            replace_items = list(ruledata['replaceinname'].items())

            def action(package, package_context, match_context):
                for pattern, replacement in replace_items:
                    package.effname = package.effname.replace(pattern, replacement)

            self.actions.append(action)

        if 'tolowername' in ruledata:
            def action(package, package_context, match_context):
                package.effname = package.effname.lower()

            self.actions.append(action)

        if 'warning' in ruledata:
            def action(package, package_context, match_context):
                print('Rule warning for {} in {}: {}'.format(package.name, package.repo, ruledata['warning']), file=sys.stderr)

            self.actions.append(action)

    def match(self, package, package_context):
        match_context = MatchContext()

        for matcher in self.matchers:
            if not matcher(package, package_context, match_context):
                return None

        self.matches += 1

        return match_context

    def apply(self, package, package_context, match_context):
        for action in self.actions:
            action(package, package_context, match_context)
