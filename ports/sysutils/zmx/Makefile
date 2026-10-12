ONLY_FOR_ARCHS =	amd64 arm64

COMMENT =	session persistence for terminal processes

# TODO: select an upstream revision containing the PTY fixes from PR #277.
ZMX_COMMIT =	2d23c0d440583736f365a55aa09cb2c82b0fe7fa
DISTNAME =	zmx-0.8.1pl20261003

GHOSTTY_COMMIT =	8af6897c0afc63037a8a3efee4162a380e3a4572
ARO_COMMIT =	ecbc5c799574e0da2758a961b12efa586007f03c
UUCODE_COMMIT =	2826a37a4562284fdacd8fa029d49509cc9bffcd
HIGHWAY_COMMIT =	66486a10623fa0d72fe91260f96c892e41aceb06

DIST_TUPLE =	github neurosnap zmx ${ZMX_COMMIT} .
DIST_TUPLE +=	github ghostty-org ghostty ${GHOSTTY_COMMIT} .
DIST_TUPLE +=	github vancluever arocc ${ARO_COMMIT} .

CATEGORIES =	sysutils
HOMEPAGE =	https://zmx.sh/

MAINTAINER =	Barrett Ruth <br@barrettruth.com>

# MIT, BSD, Apache 2.0, Unicode, zlib, CC0 (bundled dependencies)
PERMIT_PACKAGE =	Yes

WANTLIB +=	c m pthread util

BUILD_DEPENDS =	zig-=0.16.0:lang/zig
RUN_DEPENDS =	shells/bash

DIST_SUBDIR =	zmx
SITES.deps =	https://deps.files.ghostty.org/
DISTFILES.deps =	\
		translate_c-80f8b6e4f45a303268717d8e5f4f91d7837138bb.tar.gz \
		uucode-${UUCODE_COMMIT}.tar.gz \
		highway-${HIGHWAY_COMMIT}.tar.gz \
		wuffs-7411f488fe2e2c205c3d3b3d28638b7356522930.tar.gz \
		pixels-12207ff340169c7d40c570b4b6a97db614fe47e0d83b5801a932dcd44917424c8806.tar.gz \
		zlib-1220fed0c74e1019b3ee29edae2051788b080cd96e90d56836eea857b0b966742efb.tar.gz \
		ghostty-themes-release-20260824-153547-75c93ee.tgz

GHOSTTY_HASH =	ghostty-1.3.2-dev-5UdBC4FtYAV-PdFOt-gceWieTHLri0H4ztHtd6Tr4dGj
TRANSLATE_C_HASH = translate_c-0.0.0-Q_BUWmU6BwB_9JKG2l2W7i_mhmYWeRseTGBEHi_YlV5f
ARO_HASH =	aro-0.0.0-JSD1Qk8rOQDnuVcD4jAwMpHitA6pADRKzQ7M7hKRwxvD
UUCODE_HASH =	uucode-0.2.0-ZZjBPlK5VADj7fdoq7G8LIHzD5o6FSkcBXXrRWr4jnrA
HIGHWAY_HASH =	N-V-__8AAGmZhABbsPJLfbqrh6JTHsXhY6qCaLAQyx25e0XE
WUFFS_HASH =	N-V-__8AAP5JWgCGP_AD0teWpa4krRvE9VPZzvviGdbmN4jI
PIXELS_HASH =	N-V-__8AADYiAAB_80AWnH1AxXC0tql9thT-R-DYO1gBqTLc
ZLIB_HASH =	N-V-__8AAB0eQwD-0MdOEBmz7intriBReIsIDNlukNVoNu6o
THEMES_HASH =	N-V-__8AAGZkBACH0haGC9R-hfNPYWxu16hr-ydEsolad9GV

ZIG_PKGDIR =	${WRKBUILD}/zig-packages

MAKE_ENV +=	ZIG_GLOBAL_CACHE_DIR=${WRKBUILD}/zig-global-cache \
		ZIG_LOCAL_CACHE_DIR=${WRKBUILD}/zig-local-cache

ZIG_FLAGS =	--system ${ZIG_PKGDIR} \
		--global-cache-dir ${WRKBUILD}/zig-global-cache \
		--cache-dir ${WRKBUILD}/zig-local-cache \
		--color off \
		-j${MAKE_JOBS} \
		-Dcpu=baseline \
		-Doptimize=ReleaseSafe

# Ghostty also requests zlib, themes and Wuffs fixtures during build setup.
post-extract:
	mkdir -p ${ZIG_PKGDIR}
	mv ${WRKDIR}/ghostty-${GHOSTTY_COMMIT} \
		${ZIG_PKGDIR}/${GHOSTTY_HASH}
	mv ${WRKDIR}/translate-c ${ZIG_PKGDIR}/${TRANSLATE_C_HASH}
	mv ${WRKDIR}/arocc-${ARO_COMMIT} ${ZIG_PKGDIR}/${ARO_HASH}
	mv ${WRKDIR}/uucode-${UUCODE_COMMIT} ${ZIG_PKGDIR}/${UUCODE_HASH}
	mv ${WRKDIR}/highway-${HIGHWAY_COMMIT} ${ZIG_PKGDIR}/${HIGHWAY_HASH}
	mv ${WRKDIR}/${WUFFS_HASH} ${ZIG_PKGDIR}/${WUFFS_HASH}
	mv ${WRKDIR}/pixels-d843c2714d32e15b48b8d7eeb480295af537f877 \
		${ZIG_PKGDIR}/${PIXELS_HASH}
	mv ${WRKDIR}/zlib-1.3.1 ${ZIG_PKGDIR}/${ZLIB_HASH}
	mv ${WRKDIR}/ghostty ${ZIG_PKGDIR}/${THEMES_HASH}

do-build:
	cd ${WRKSRC} && ulimit -s 16384 && exec ${SETENV} ${MAKE_ENV} \
		${LOCALBASE}/bin/zig build ${ZIG_FLAGS} --prefix ${WRKBUILD}/stage

do-install:
	${INSTALL_PROGRAM} ${WRKBUILD}/stage/bin/zmx ${PREFIX}/bin
	${INSTALL_DATA_DIR} ${PREFIX}/share/doc/zmx
	${INSTALL_DATA} ${WRKSRC}/LICENSE ${WRKSRC}/README.md \
		${PREFIX}/share/doc/zmx

do-test:
	cd ${WRKSRC} && ulimit -s 16384 && exec ${SETENV} ${MAKE_ENV} \
		${TEST_ENV} ${LOCALBASE}/bin/zig build test ${ZIG_FLAGS}

.include <bsd.port.mk>
