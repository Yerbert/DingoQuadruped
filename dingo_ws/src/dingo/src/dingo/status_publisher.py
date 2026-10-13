from std_msgs.msg import String


class StatusPublisher:

    def __init__(self, node):
        self.status_publisher = node.create_publisher(String, "/robot_status_messages", 10)

    def publish_message(self, message):
        self.status_publisher.publish(String(data=str(message)))
