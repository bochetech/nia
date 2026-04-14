import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

const TENANT_MANAGER_URL =
  process.env.TENANT_MANAGER_URL || "http://localhost:8003";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      name: "NIA Admin",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        try {
          const res = await fetch(`${TENANT_MANAGER_URL}/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
              ttl_minutes: 1440,
            }),
          });

          if (!res.ok) return null;

          const data = await res.json();
          return {
            id: data.subject,
            email: data.subject,
            name: data.subject,
            role: data.role,
            accessToken: data.access_token,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as any).accessToken;
        token.role = (user as any).role;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).role = token.role;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },
});
