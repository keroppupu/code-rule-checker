package com.example.service;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

public class UserService {

    // 違反: ハードコードされた機密情報 (JAVA-SEC-002)
    private static final String DB_URL = "jdbc:postgresql://localhost:5432/mydb";
    private static final String DB_USER = "admin";
    private static final String DB_PASS = "SuperSecretPassword123!";

    // 違反: 命名規約違反 (lowerCamelCaseではなくSnakeCase) (JAVA-CONV-001)
    public void find_user_by_name(String user_name) {
        Connection conn = null;
        Statement stmt = null;
        ResultSet rs = null;

        try {
            conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASS);
            stmt = conn.createStatement();

            // 違反: SQLインジェクション (文字列連結によるクエリ構築) (JAVA-SEC-001)
            String sql = "SELECT id, name, email FROM users WHERE name = '" + user_name + "'";
            rs = stmt.executeQuery(sql);

            while (rs.next()) {
                String email = rs.getString("email");
                // 違反: 変数.equals(定数) による NullPointerException のリスク (JAVA-CONV-001)
                if (user_name.equals("admin")) {
                    System.out.println("管理者ユーザーを検出: " + email);
                } else {
                    System.out.println("一般ユーザー: " + email);
                }
            }
            // 違反: try-with-resources を使っておらず、例外発生時にリソースリークの危険性あり (JAVA-RES-001)
            rs.close();
            stmt.close();
            conn.close();
        } catch (Exception e) {
            // 違反: e.printStackTrace() のみでロガーを使用していない (JAVA-EXC-001)
            e.printStackTrace();
        }
    }
}
