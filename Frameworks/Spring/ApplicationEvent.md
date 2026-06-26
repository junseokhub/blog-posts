---
title: [Spring] 스프링 애플리케이션 이벤트 (ApplicationEventPublisher)
thumbnail: /blog/images/spring.png
date: 2026-06-20
---

## Intro
한 작업이 끝나면 거기 딸린 일들이 줄줄이 따라붙는 경우가 많다. 핵심 작업은 하나인데, 그 사실에 반응해야 하는 부가작업은 많다. 이걸 전부 핵심 코드 안에 직접 호출로 박으면, 핵심 로직은 자기 일이 아닌 것들로 가득해지고 부가작업이 하나 늘 때마다 핵심 코드를 다시 연다.이때 핵심 로직은 무슨 일이 일어났다라는 사실만 알리고, 나머지는 그 사실을 듣고 알아서 하게 떼어내는 게 스프링 애플리케이션 이벤트다.
 
이 글은 그 도구인 `ApplicationEventPublisher`가 무엇이고, 발행·구독 방법에는 뭐가 있고, 동기·비동기와 트랜잭션에 어떻게 엮이고, 어디까지가 한계인지를 다룬다.
 
---
 
## 핵심 로직에 들러붙는 부가작업
 
### 직접 호출의 한계
 
부가작업을 직접 호출로 엮으면, 핵심 로직이 부가작업을 전부 알아야 한다.
 
```java
@Service
@RequiredArgsConstructor
public class SomeService {
 
    private final SomeRepository repository;
    private final TaskA taskA;   // 부가작업
    private final TaskB taskB;   // 부가작업
 
    @Transactional
    public void doSomething(Command cmd) {
        Entity entity = repository.save(Entity.from(cmd));  // 핵심
        taskA.run(entity);                                  // 곁다리
        taskB.run(entity);                                  // 곁다리
    }
}
```
 
문제는 코드가 더러운 게 아니다. 부가작업이 하나 늘 때마다 `SomeService`를 연다라는 게 문제다. `TaskA`, `TaskB`가 핵심 서비스의 의존성으로 줄줄이 딸려오고, 핵심 로직 하나 테스트하려면 그것들을 전부 mocking해야 한다. 핵심 로직이 곁다리의 변경에 끌려다닌다.
 
### 방향을 뒤집어볼까?
 
직접 호출은 부르는 쪽이 받는 쪽을 안다.이걸 뒤집어 생각해보면, 부르는 쪽은 이런 일이 일어났다고 방송만 하고, 받는 쪽이 알아서 구독하게 하면 의존이 끊긴다. 이 뒤집기가 옵저버 패턴이고, 스프링이 `ApplicationEventPublisher`로 기본 제공한다.
 
```
[직접 호출]   SomeService -- 알아야 함 --> TaskA / TaskB
[이벤트]      SomeService -- 일어났다 --> (누가 듣는지 모름)
                                            -> TaskA / TaskB 가 알아서 구독
```
 
---
 
## 스프링 이벤트란?
 
같은 JVM 안에서 도는 옵저버 패턴이다.
 
**이벤트(event)** 
- 무슨 일이 일어났다는 사실을 담은 객체.
**발행자(publisher)** 
- `ApplicationEventPublisher`. 이벤트를 쏜다.
**리스너(listener)**
- `@EventListener`. 이벤트를 듣고 처리한다.

### 이벤트 객체
 
예전엔 `ApplicationEvent`를 상속해야 했지만, Spring 4.2부터는 그냥 POJO면 된다.불변이 자연스러우니 `record`가 잘 맞는다. 이벤트는 이미 일어난 사실이라 과거형으로 이름 짓는게 좋다.
 
```java
public record SomethingHappenedEvent(Long id, String payload) {}
```
 
### 발행
 
`ApplicationEventPublisher`를 주입받아 `publishEvent`만 부르면 된다. `ApplicationContext`가 이 인터페이스를 구현하므로 빈으로 바로 주입된다.
 
```java
@Service
@RequiredArgsConstructor
public class SomeService {
 
    private final SomeRepository repository;
    private final ApplicationEventPublisher eventPublisher;  // 스프링이 주입
 
    @Transactional
    public void doSomething(Command cmd) {
        Entity entity = repository.save(Entity.from(cmd));
        eventPublisher.publishEvent(new SomethingHappenedEvent(entity.getId(), cmd.payload()));
    }
}
```
 
`SomeService`는 이제 `TaskA`, `TaskB`를 모른다.
의존성에서 다 사라졌다.
 
### 구독
 
리스너 메서드에 `@EventListener`를 붙이고, 파라미터 타입으로 어떤 이벤트를 들을지 정한다.
 
```java
@Component
public class SomeEventHandler {
 
    @EventListener
    public void handleA(SomethingHappenedEvent event) {  // 타입 매칭으로 호출됨
        // 부가작업 A
    }
 
    @EventListener
    public void handleB(SomethingHappenedEvent event) {
        // 부가작업 B
    }
}
```
 
부가작업을 추가할 땐 리스너 하나를 더할 뿐, 핵심 코드는 안 건드린다.결합이 끊긴 효과가 여기서 나온다.
 
---
 
## 리스너 종류
 
`@EventListener`만 알아도 되지만, 쓸 만한 변형이 몇 개 있다.
 
**여러 타입 한 메서드로**
```java
@EventListener({SomethingHappenedEvent.class, AnotherEvent.class})
public void handle(Object event) { ... }
```
 
**조건부 (SpEL)** -> 특정 조건만 듣는다.
```java
@EventListener(condition = "#event.payload() == 'IMPORTANT'")
public void handleImportant(SomethingHappenedEvent event) { ... }
```
 
**리턴값으로 이벤트 체이닝** —> 리스너가 값을 리턴하면 그게 새 이벤트로 다시 발행된다. `void`나 `null`이면 아무 일 없다.
```java
@EventListener
public AnotherEvent handle(SomethingHappenedEvent event) {
    // ...
    return new AnotherEvent(...);  // 이게 또 발행되어 다음 리스너로
}
```
 
**실행 순서** 
- 같은 이벤트를 듣는 리스너가 여럿이면 순서는 보장되지 않는다. 순서가 필요하면 `@Order`로 못 박는다(숫자 작을수록 먼저).
```java
@Order(1)
@EventListener
public void first(SomethingHappenedEvent event) { ... }
```
 
> 옛날 방식인 `ApplicationListener<E>` 인터페이스 구현도 여전히 동작하지만, 지금은 `@EventListener`가 표준이다. 스프링 내부 생명주기 이벤트(`ContextRefreshedEvent` 등)를 듣는 특수한 경우가 아니면 인터페이스 구현은 쓸 일이 거의 없다.
 
---
 
## 트랜잭션과의 관계
 
여기를 모르고 쓰면 사고 난다.
 
### 기본은 동기 + 같은 트랜잭션
 
`publishEvent`는 발행한 스레드에서, 그 자리에서 즉시 리스너를 부른다. 별도 스레드도, 큐도 없다. 그래서 발행 시점이 트랜잭션 안이면, 리스너도 같은 트랜잭션 안에서 돈다.
 
- 리스너에서 한 DB 작업은 발행자의 트랜잭션과 함께 커밋/롤백된다
- 리스너에서 예외를 던지면 발행자에게 전파되어 트랜잭션이 통째로 롤백된다
즉 기본 `@EventListener`는 부가작업이라기보다 핵심 트랜잭션의 일부에 가깝다. 여기서 외부 시스템을 건드리는 작업(외부 API 호출 등)을 하면, 그쪽이 삐끗할 때 핵심 트랜잭션까지 같이 롤백된다.
 
### @TransactionalEventListener
 
대부분의 부가작업은 핵심 작업이 실제로 커밋된 뒤에만 일어나야 한다. 동기 리스너는 커밋 전에 돌기 때문에, 외부로 내보내는 작업을 여기서 하면 트랜잭션이 막판에 롤백돼도 그 작업은 이미 벌어진 뒤다. —> 일어나지 않은 일을 외부에 알린 꼴이다.
 
`@TransactionalEventListener`는 리스너를 트랜잭션 단계(phase)에 묶어서 실행한다.
 
```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handle(SomethingHappenedEvent event) {
    // 커밋이 확실히 끝난 뒤에만 실행
}
```
 
phase는 네 가지다.
 
- `BEFORE_COMMIT` — 커밋 직전 (아직 같은 트랜잭션 안)
- `AFTER_COMMIT` — 커밋 성공 후 (기본값)
- `AFTER_ROLLBACK` — 롤백 후
- `AFTER_COMPLETION` — 커밋이든 롤백이든 끝난 후
```
   -------- 트랜잭션 ---------
   publish ... BEFORE_COMMIT | commit | AFTER_COMMIT
                             ---------- AFTER_ROLLBACK / AFTER_COMPLETION
```
 
### @TransactionalEventListener의 함정
 
**트랜잭션이 없으면 그냥 안 돈다.** 
- `@TransactionalEventListener`는 활성 트랜잭션이 있을 때만 동작한다. 발행 지점에 트랜잭션이 없으면 리스너는 조용히 스킵된다. 테스트나 배치에서 "왜 리스너가 안 불리지?" 하면 십중팔구 이거다. 트랜잭션 밖에서도 돌게 하려면 `fallbackExecution = true`를 켠다.
 
**AFTER_COMMIT에서 DB를 쓰면 안 먹힐 수 있다.** 
- 커밋이 이미 끝난 뒤라, 여기서 그냥 DB 작업을 하면 묶일 트랜잭션이 없다. 새 트랜잭션을 명시해야 한다.
 
```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
@Transactional(propagation = Propagation.REQUIRES_NEW)  // 새 트랜잭션
public void handle(SomethingHappenedEvent event) { ... }
```
 
---
 
## 동기 vs 비동기
 
`TransactionEventListener`는 기본이 동기라 리스너가 느리면 발행자도 그만큼 느려진다. 외부 API 호출처럼 느린 부가작업은 비동기로 빼는 게 낫다. `@EnableAsync`를 켜고 리스너에 `@Async`를 붙이면 전용 스레드풀에서 돈다.
 
```java
@Async("eventExecutor")   // 전용 Executor 빈 지정 (공용 풀 공유 금지)
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handle(SomethingHappenedEvent event) { ... }
```
 
비동기는 공짜가 아니다. 스레드가 갈리면서 세 가지가 따라온다.
 
**트랜잭션 컨텍스트가 안 넘어간다.** 
- 새 스레드엔 영속성 컨텍스트가 없다. 리스너 안에서 lazy 로딩하면 터진다. 필요한 값은 이벤트에 다 담아 보낸다.
**예외가 발행자에게 전파되지 않는다.**
- `void` 비동기 메서드의 예외는 호출자에게 안 간다.
- `AsyncUncaughtExceptionHandler`를 등록해 따로 잡아야 조용히 삼켜지지 않는다.
**앱이 죽으면 큐에 있던 작업은 사라진다.** 
- 비동기는 메모리 안 큐다. 영속성이 없다.
---
 
## 한계
**프로세스 경계를 못 넘는다.** 
- 같은 JVM 안에서만 돈다. 다른 서비스로 보내려면 브로커(Kafka 등)가 필요하다.
**영속성이 없다.** 
- 앱이 죽으면 발행 중이던 이벤트도, 비동기 큐에 쌓인 이벤트도 그대로 증발한다.
  
그래서 `@TransactionalEventListener(AFTER_COMMIT)`에서 외부로 직접 발행해도 유실 구멍이 남는다. 커밋은 됐는데 리스너가 발행하기 직전에 인스턴스가 죽으면 그 이벤트는 영영 안 나간다. 스프링 이벤트 단독으로는 보냈다는 보장을 줄 수 없다.
 
여기서부터는 스프링 이벤트의 일이 아니다. 프로세스를 넘기는 건 메시지 브로커의 몫이고, 죽어도 이벤트가 살아남도록 발행을 보장하는 건 별도 패턴의 몫이다. 스프링 이벤트가 그 패턴들과 잘 맞물리는 도구이긴 한데, 그 조합은 자세히 나중에 따로 다뤄 볼 예정이다.
 
---
 
## 언제 쓸까? / 언제 쓰지 말까?
 
### 쓰면 좋은 경우
- 같은 앱 안에서 모듈 간 결합도를 낮추고 싶을 때.
- 핵심 로직에서 부가작업(side effect)을 떼어낼 때.
- 도메인 이벤트를 트랜잭션 경계와 묶어서 처리할 때. (`@TransactionalEventListener`)
### 안 쓰는 / 못 쓰는 경우
- 프로세스 밖으로 내보낼 때 -> 브로커
- 유실이 치명적인데 이것만으로 보장하려 할 때 -> 발행 보장 패턴이 필요
- 흐름이 단순해서 직접 호출이 더 읽기 쉬울 때. 이벤트는 누가 듣는지를 숨기므로, 굳이 안 끊어도 될 결합까지 이벤트로 흩으면 추적만 어려워진다
  
---
 
## 장단점
 
**장점**
- 추가 인프라가 0이다. 스프링만 있으면 된다
- 발행자가 리스너를 몰라 결합도가 낮다. 부가작업 추가가 핵심 코드를 안 건드린다
- 트랜잭션 단계에 정밀하게 묶을 수 있다 (`@TransactionalEventListener`)
- 도메인 이벤트를 표현하기에 자연스럽다 (DDD)
**단점**
- 인프로세스라 프로세스를 못 넘고, 영속성이 없다. (유실 보장 불가)
- 이벤트 흐름이 코드에 안 드러난다. 누가 이걸 듣는가를 IDE로 바로 못 보고, 디버깅이 어려워진다.
- 비동기로 가면 트랜잭션 전파/예외 전파/유실을 직접 관리해야 한다.
- 남발하면 흐름이 이벤트로 흩어져 추적 지옥이 된다.
---
 
## 정리
 
**스프링 이벤트** 
- 같은 JVM 안 옵저버 패턴. 발행자는 사실만 알리고, 리스너가 듣는다.(`ApplicationEventPublisher` + `@EventListener`)
듣는 법 
- 기본 `@EventListener`, 트랜잭션 단계에 묶는 `@TransactionalEventListener`(`AFTER_COMMIT`이 보통)
**트랜잭션** 
- 기본은 **동기 + 같은 트랜잭션**. 리스너 예외가 발행자 트랜잭션을 롤백시킨다. "커밋 후"가 필요하면 `AFTER_COMMIT`(+ DB 쓰기는 `REQUIRES_NEW`)
**한계**
- 인프로세스·비영속. 프로세스를 넘거나 유실을 보장하는 건 스프링 이벤트의 일이 아니다.(브로커·발행 보장 패턴의 몫)

## 마무리
스프링 이벤트는 한 프로세스 안의 결합을 끊는 도구일 뿐, 유실을 막아주는 도구가 아니다. 이 선만 분명히 그으면, 어디까지 이걸로 풀고 어디서부터 다른 도구를 꺼내야 하는지가 또렷해지지 않을까 싶다.