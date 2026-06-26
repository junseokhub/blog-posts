---
title: [Spring] Gradle MSA에서 모듈을 어떻게 해야할까?
thumbnail: /blog/images/spring.png
date: 2026-06-18
---

SpringBoot + Gradle로 MSA를 구성할 때 가장 먼저 맞닥뜨리는 문제가 있다.

> 공통 설정을 어디에 두고, 어떻게 각 모듈에 적용할까?

Java Toolchain 버전, Lombok, 테스트 설정, BOM같은 것들은 서비스마다 복붙하다보면 어느샌가 관리가 힘들어진다. 먼저 이걸 해결할 수 있는 방법은 크게 4가지가 있다.

1. **Cross-project Configuration** (Root build.gradle에서 서브 프로젝트에 주입)

2\. **buildSrc** Convention Plugin

3\. **build-logic** Convention Plugin (Composite Build)

4\. **각 모듈에 독립적으로 설정**

지금부터는 각각 어떤 방식인지, 각 방식에 어떤 장단점이 있는지 알아보려고 한다.

---

## Cross-project Configuration

`Root build.gradle`에서 서브 프로젝트를 필터링해 설정을 밀어 넣는 방식이다.

### Groovy DSL

```
// build.gradle (루트)
subprojects {
    apply plugin: 'java'
    apply plugin: 'org.springframework.boot'
    apply plugin: 'io.spring.dependency-management'

    dependencies {
        compileOnly 'org.projectlombok:lombok'
        annotationProcessor 'org.projectlombok:lombok'
    }
}

// 또는 필터링해서 일부에만 적용
configure(subprojects.findAll { it.parent?.name == 'services' }) {
    apply plugin: 'org.springframework.boot'
}
```

### Kotlin DSL

```
// build.gradle.kts (루트)
subprojects {
    apply(plugin = "java")
    apply(plugin = "org.springframework.boot")
    apply(plugin = "io.spring.dependency-management")

    dependencies {
        "compileOnly"("org.projectlombok:lombok")
        "annotationProcessor"("org.projectlombok:lombok")
    }
}

// 또는 필터링
configure(subprojects.filter { it.parent?.name == "services" }) {
    apply(plugin = "org.springframework.boot")
}
```

### 각 서비스 모듈

```
// services/xxx-service/build.gradle
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
}
```

```
// services/xxx-service/build.gradle.kts
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
}
```

루트에서 공통 설정을 주입하기 때문에 각 서비스 모듈은 자기 의존성만 선언하면 된다.

### 장점

-   별도 디렉토리나 파일 없이 루트 한 곳에서 모든 설정 관리
-   설정이 어디에 있는지 바로 알 수 있음
-   작은 프로젝트에서 빠르게 시작 가능

### 단점

-   Gradle 공식 비권장 방식이다. [Gradle 문서](https://docs.gradle.org/current/userguide/sharing_build_logic_between_subprojects.html)는 명시적으로 이 방식을 피하라고 한다.
-   루트가 서브프로젝트를 알아야 하므로 프로젝트 격리(Project Isolation)가 깨진다 -> Configuration Cache, Isolated Projects 같은 최적화와 호환이 안된다.
-   병렬 빌드가 제대로 동작하지 않는다.
-   어떤 모듈에 어떤 설정이 적용됐는지 루트를 봐야만 알 수 있다.
-   모듈이 많아질수록 루트 build.gradle이 복잡해진다.

---

## buildSrc Convention Plugin

buildSrc는 Gradle이 자동으로 인식하는 특수 디렉토리다. 이 안에 Convention Plugin을 만들면 모든 서브프로젝트에서 플러그인 ID로 참조할 수 있다.

### 디렉토리 구조

```
my-msa/
├── buildSrc/
│   ├── build.gradle (또는 .kts)
│   └── src/main/groovy/ (또는 kotlin/)
│       ├── myapp.java-base-conventions.gradle
│       ├── myapp.library-conventions.gradle
│       └── myapp.application-conventions.gradle
├── libs/
│   └── common-web/
└── services/
    └── payment-service/
```

### buildSrc/build.gradle

#### Groovy DSL

```
plugins {
    id 'groovy-gradle-plugin'
}

repositories {
    mavenCentral()
    gradlePluginPortal()
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-gradle-plugin:3.5.0'
    implementation 'io.spring.gradle:dependency-management-plugin:1.1.7'
}
```

#### Kotiln DSL

```
plugins {
    `kotlin-dsl`
}

repositories {
    mavenCentral()
    gradlePluginPortal()
}

dependencies {
    implementation("org.springframework.boot:spring-boot-gradle-plugin:3.5.0")
    implementation("io.spring.gradle:dependency-management-plugin:1.1.7")
}
```

### Convention Plugin 작성

#### Groovy DSL

```
// buildSrc/src/main/groovy/myapp.java-base-conventions.gradle
import org.springframework.boot.gradle.plugin.SpringBootPlugin

plugins {
    id 'java'
    id 'io.spring.dependency-management'
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}

dependencies {
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}
```

```
// buildSrc/src/main/groovy/myapp.library-conventions.gradle
plugins {
    id 'java-library'
    id 'myapp.java-base-conventions'
}
```

```
// buildSrc/src/main/groovy/myapp.application-conventions.gradle
plugins {
    id 'myapp.java-base-conventions'
    id 'org.springframework.boot'
}
```

#### Kotlin DSL

```
// buildSrc/src/main/kotlin/myapp.java-base-conventions.gradle.kts
import org.springframework.boot.gradle.plugin.SpringBootPlugin

plugins {
    java
    id("io.spring.dependency-management")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}

dependencies {
    "compileOnly"("org.projectlombok:lombok")
    "annotationProcessor"("org.projectlombok:lombok")
    "testImplementation"("org.springframework.boot:spring-boot-starter-test")
}
```

```
// buildSrc/src/main/kotlin/myapp.library-conventions.gradle.kts
plugins {
    `java-library`
    id("myapp.java-base-conventions")
}
```

```
// buildSrc/src/main/kotlin/myapp.application-conventions.gradle.kts
plugins {
    id("myapp.java-base-conventions")
    id("org.springframework.boot")
}
```

### 각 모듈에서 사용

#### Groovy

```
// libs/common-web/build.gradle
plugins {
    id 'myapp.library-conventions'
}

dependencies {
    api 'org.springframework.boot:spring-boot-starter-web'
}
```

```
// services/xxx-service/build.gradle
plugins {
    id 'myapp.application-conventions'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation project(':libs:common-web')
}
```

#### Kotlin

```
// libs/common-web/build.gradle.kts
plugins {
    id("myapp.library-conventions")
}

dependencies {
    api("org.springframework.boot:spring-boot-starter-web")
}
```

```
// services/xxx-service/build.gradle.kts
plugins {
    id("myapp.application-conventions")
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation(project(":libs:common-web"))
}
```

### 장점

-   별도 설정 없이 buildSrc 디렉토리만 만들면 Gradle이 자동 인식
-   Cross-project Configuration보다 각 모듈이 독립적으로 선언 → 격리도 향상
-   Convention Plugin 단위로 역할이 명확하게 분리됨
-   각 모듈의 build.gradle이 매우 짧아짐

### 단점

-   buildSrc 안 파일이 단 하나라도 바뀌면 **전체 프로젝트 빌드 캐시가 무효화**된다
-   buildSrc의 클래스로더가 메인 빌드와 분리되지 않아 의존성이 노출될 수 있다
-   모듈이 수십 개 이상이고 Convention Plugin을 자주 수정하면 빌드 시간이 체감될 수 있다

---

## build-logic Convention Plugin (Composite Build)

buildSrc와 구조는 동일하지만, settings.gradle에 includeBuild("build-logic")으로 직접 등록하는 방식이다. Gradle 공식 문서가 명시적으로 권장하는 방법이다.

### 디렉토리 구조

```
my-msa/
├── settings.gradle (또는 .kts)        // includeBuild("build-logic") 등록
├── build.gradle (또는 .kts)
├── build-logic/
│   ├── settings.gradle (또는 .kts)    // build-logic 자체 프로젝트 선언
│   ├── build.gradle (또는 .kts)       // Spring Boot 버전 등 선언
│   └── src/main/groovy/ (또는 kotlin/)
│       ├── myapp.java-base-conventions.gradle (.kts)
│       ├── myapp.library-conventions.gradle (.kts)
│       └── myapp.application-conventions.gradle (.kts)
├── libs/
└── services/
```

### Root setting.gradle

#### Groovy DSL

```
// settings.gradle (Root)
rootProject.name = 'my-msa'

includeBuild 'build-logic'   // 이 줄이 없으면 build-logic이 인식되지 않는다

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

include(
    'libs:common-web',
    'services:xxx-service',
    'services:xxx1-service' //.....
)
```

#### Kotiln DSL

```
// settings.gradle.kts (Root)
rootProject.name = "my-msa"

includeBuild("build-logic")

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

include(
    'libs:common-web',
    'services:xxx-service',
    'services:xxx1-service' //.....
)
```

### build-logic 자체 설정

#### Groovy DSL

```
// build-logic/settings.gradle
rootProject.name = 'build-logic'
```

```
// build-logic/build.gradle
plugins {
    id 'groovy-gradle-plugin'
}

repositories {
    mavenCentral()
    gradlePluginPortal()
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-gradle-plugin:3.5.0'
    implementation 'io.spring.gradle:dependency-management-plugin:1.1.7'
}
```

#### Kotlin DSL

```
// build-logic/settings.gradle.kts
rootProject.name = "build-logic"
```

```
// build-logic/build.gradle.kts
plugins {
    `kotlin-dsl`   // 이게 빠지면 Convention Plugin이 생성되지 않는다
}

repositories {
    mavenCentral()
    gradlePluginPortal()
}

dependencies {
    implementation("org.springframework.boot:spring-boot-gradle-plugin:3.5.0")
    implementation("io.spring.gradle:dependency-management-plugin:1.1.7")
}
```

Convention Plugin 작성 방식과 각 모듈에서 사용하는 방식은 buildSrc와 동일하다. 차이는 Gradle이 자동 인식하느냐, settings.gradle에 직접 등록하느냐뿐이다.

### buildSrc vs build-logic 차이 요약

| **항목** | **buildSrc** | **build-logic** |
| --- | --- | --- |
| 인식 방식 | Gradle 자동 인식 | includeBuild()로 직접 등록 |
| 캐시 무효화 | 파일 변경 시 전체 캐시 무효화 | 변경된 부분만 무효화 |
| 클래스로더 격리 | 메인 빌드와 공유 | 독립적으로 격리 |
| 설정 복잡도 | 낮음 (디렉토리만 생성) | 약간 높음 (settings.gradle 추가 필요) |
| Gradle 권장 여부 | 단순 프로젝트에 적합 | 공식 권장 |

### 장점

-   buildSrc의 캐시 무효화 문제가 없다 → 빌드 속도 유지
-   클래스로더가 격리되어 의존성 충돌 가능성이 낮다
-   각 모듈이 필요한 Convention Plugin을 직접 선언 → 설정 주입이 아닌 선언
-   Gradle 공식 권장 방식

### 단점

-   build-logic/settings.gradle 파일을 추가로 관리해야 한다
-   includeBuild() 등록을 빠뜨리면 Plugin not found 에러가 나고, 처음에 당황할 수 있다
-   buildSrc보다 초기 설정이 살짝 더 많다

---

## 각 모듈이 독립적으로 설정

말 그대로 공통화 없이 각 모듈이 모든 설정을 직접 선언하는 방식이다.

### 장점

-   각 모듈이 완전히 독립적 → 다른 모듈 변경에 전혀 영향받지 않음
-   빌드 파일만 보면 그 모듈에 무엇이 적용됐는지 전부 알 수 있음
-   모듈 간 의존 없이 추출하거나 다른 프로젝트로 이동하기 쉬움

### 단점

-   Spring Boot 버전을 올릴 때 모든 모듈을 일일이 수정해야 함
-   Lombok, Toolchain 등 공통 설정이 모든 파일에 반복됨
-   모듈이 10개 이상이면 관리 비용이 급격히 증가함
-   실수로 한 모듈만 버전이 달라지는 문제가 생기기 쉬움

---

## 라이브러리 모듈에서 BOM은 어떻게 가져올까?

서비스 모듈은 org.springframework.boot 플러그인이 BOM을 자동으로 끌어온다. 그런데 실행 가능한 JAR가 필요 없는 라이브러리 모듈은 어떻게 해야 할까?

### boot 플러그인을 붙이고 bootJar를 비활성화 (비권장)

```
// Groovy
plugins {
    id 'org.springframework.boot'
    id 'io.spring.dependency-management'
}

bootJar.enabled = false
jar.enabled = true
```

```
// Kotlin DSL
plugins {
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

tasks.withType<BootJar> { enabled = false }
tasks.withType<Jar> { enabled = true }
```

### BOM을 버전 하드코딩으로 직접 import

```
// Groovy
dependencyManagement {
    imports {
        mavenBom 'org.springframework.boot:spring-boot-dependencies:3.5.0'
    }
}
```

```
// Kotlin DSL
dependencyManagement {
    imports {
        mavenBom("org.springframework.boot:spring-boot-dependencies:3.5.0")
    }
}
```

버전을 직접 하드코딩해야 해서 루트에서 Spring Boot 버전을 올려도 여기를 따로 바꿔야 한다.

### Convention Plugin에서 SpringBootPlugin.BOM\_COORDINATES 사용 (권장)

```
// buildSrc 또는 build-logic의 myapp.java-base-conventions.gradle
import org.springframework.boot.gradle.plugin.SpringBootPlugin

plugins {
    id 'java'
    id 'io.spring.dependency-management'
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}
```

```
// buildSrc 또는 build-logic의 myapp.java-base-conventions.gradle.kts
import org.springframework.boot.gradle.plugin.SpringBootPlugin

plugins {
    java
    id("io.spring.dependency-management")
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}
```

SpringBootPlugin.BOM\_COORDINATES는 build-logic/build.gradle에 선언한 spring-boot-gradle-plugin 버전과 자동으로 연동된다. 버전을 한 곳에서만 관리하면 전체에 반영된다.

---

## api() vs implementation()

java-library 플러그인을 쓰면 의존성 선언이 두 가지로 나뉜다.

```
// Groovy
dependencies {
    // 이 라이브러리를 사용하는 모듈에도 전파됨
    api 'org.springframework.boot:spring-boot-starter-web'

    // 이 라이브러리 내부에서만 사용, 외부에 노출 안 됨
    implementation 'com.fasterxml.jackson.core:jackson-databind'
}
```

```
// Kotlin DSL
dependencies {
    // 이 라이브러리를 사용하는 모듈에도 전파됨
    api("org.springframework.boot:spring-boot-starter-web")

    // 이 라이브러리 내부에서만 사용, 외부에 노출 안 됨
    implementation("com.fasterxml.jackson.core:jackson-databind")
}
```

공개 API에 타입이 노출되는 의존성은 api(), 내부 구현에만 쓰이는 건 implementation()이다. implementation()을 쓸수록 의존성이 불필요하게 전파되지 않아 컴파일 범위가 좁아지고 빌드가 빨라진다.

---

## 그래서 어떤 걸 선택하면 좋을까?

상황에 따라 다르다.

**서비스가 3개 이하, 빠르게 프로토타이핑**이 목적이라면 Cross-project Configuration이나 독립 설정도 나쁘지 않다. 어차피 금방 버린다.

**서비스가 늘어날 것 같고, 팀이 같이 쓰는 공유 프로젝트**라면 build-logic Convention Plugin이 적합하다. 처음 설정이 조금 더 필요하지만 이후 모듈 추가가 훨씬 간단해진다.

**혼자 쓰고 Convention Plugin 개념만 익혀보고 싶다면** buildSrc로 시작해도 충분하다. 구조는 build-logic과 동일해서 나중에 마이그레이션도 어렵지 않다.

직접 적용해보니 build-logic 방식에서 새 서비스나 라이브러리를 추가할 때 할 일이 두 가지로 줄었다. settings.gradle에 모듈 선언하고, build.gradle에 Convention Plugin ID 한 줄 쓰는 게 전부다. 나머지(Toolchain, BOM, Lombok, 테스트 설정)는 자동으로 따라온다.

---

## 마치며

Gradle 멀티모듈 구조에서 캡슐화 전략을 고를 때 핵심은 두 가지다.

-   **공통 설정을 어디에 둘 것인가** (루트 주입 vs Convention Plugin)
-   **각 모듈이 얼마나 독립적으로 선언할 것인가** (주입받는 구조 vs 직접 선언하는 구조)

Cross-project Configuration은 빠르지만 Gradle이 비권장하고 확장성이 나쁘다. 독립 설정은 격리는 완벽하지만 반복이 심하다. Convention Plugin(buildSrc 또는 build-logic)은 그 사이에서 실용적인 균형점이다. 그중에서도 build-logic이 캐시 효율과 격리 면에서 한 단계 더 낫다.

결국 어떤 방법이든 트레이드오프가 있고, 팀 규모와 프로젝트 규모에 맞게 선택하면 된다.