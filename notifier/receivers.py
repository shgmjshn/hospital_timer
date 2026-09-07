"""Queue Store のシグナルと Notifier のつなぎ込み。"""

from django.dispatch import receiver

from queue_store.signals import exam_finished


@receiver(exam_finished, dispatch_uid="notifier.final_call_on_exam_finished")
def send_final_call_on_exam_finished(sender, entry, **kwargs):
    """診察完了の記録をトリガーに、次の患者へ確定呼出を送る。

    完了記録と同じトランザクションの中で送る。記録が巻き戻れば送信記録も一緒に消え、
    「送ったのに記録がない」状態を残さない。
    """
    from notifier.dispatcher import dispatch_final_call

    dispatch_final_call()
