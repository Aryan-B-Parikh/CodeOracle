package com.example.nested;

public class Outer {

    public class Inner {
        public int run() {
            return step();
        }

        public int step() {
            return 1;
        }
    }

    public static class StaticNested {
        public String name() {
            return "static";
        }
    }

    public Inner make() {
        return new Inner();
    }
}
