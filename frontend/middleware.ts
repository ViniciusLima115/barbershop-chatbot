import { NextRequest, NextResponse } from "next/server";


export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isProtectedPath =
    pathname === "/" ||
    pathname === "/agenda" ||
    pathname.startsWith("/agenda/") ||
    pathname === "/gestao" ||
    pathname.startsWith("/gestao/") ||
    pathname === "/configuracoes" ||
    pathname.startsWith("/configuracoes/") ||
    pathname.startsWith("/admin");

  if (isProtectedPath) {
    const token = req.cookies.get("token")?.value;
    if (!token) {
      const url = new URL("/login", req.url);
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}


export const config = {
  matcher: ["/", "/agenda/:path*", "/gestao/:path*", "/configuracoes", "/configuracoes/:path*", "/admin/:path*"],
};
